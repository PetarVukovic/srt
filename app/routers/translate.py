"""Translation API endpoints."""

import os
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, HTTPException
from app.core.config import (
    Settings,
    get_settings,
    TARGET_LANGUAGES,
)
from app.services.openai import OpenAIBatchTranslationService

router = APIRouter(prefix="/batch/translate", tags=["translate"])


@router.post("/batch-translate-srt")
async def batch_translate_srt(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] | UploadFile = File(...),
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
):
    settings: Settings = get_settings()

    # --- parse languages ---
    if languages:
        language_list = [
            lang.strip()
            for lang in languages.split(",")
            if lang.strip()
        ]
    else:
        language_list = TARGET_LANGUAGES

    # --- ensure directories ---
    os.makedirs(settings.input_folder, exist_ok=True)
    os.makedirs(settings.output_folder, exist_ok=True)
    os.makedirs(settings.temp_folder, exist_ok=True)

    service = OpenAIBatchTranslationService(settings)

    accepted_files = []

    for file in files:
        if not file.filename.lower().endswith(".srt"):
            continue  # ili raise ako želiš strogo

        base_name = os.path.splitext(file.filename)[0]
        input_path = os.path.join(settings.input_folder, f"{base_name}.srt")

        try:
            content = await file.read()
            with open(input_path, "wb") as f:
                f.write(content)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save uploaded file {file.filename}: {str(e)}"
            )

        # --- enqueue background job per file ---
        background_tasks.add_task(
            service.translate_and_notify,
            input_path=input_path,
            base_name=base_name,
            languages=language_list,
            folder_id=folder_id,
        )

        accepted_files.append(file.filename)

    return {
        "status": "accepted",
        "files_count": len(accepted_files),
        "files": accepted_files,
        "languages_count": len(language_list),
        "message": "Batch translation jobs scheduled",
    }