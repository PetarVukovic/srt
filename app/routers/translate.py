"""Translation API endpoints."""

import os
from typing import Optional
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
    file: UploadFile = File(...),
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

    # --- save input file ---
    base_name = os.path.splitext(file.filename)[0] # razdvaja ime od ekstenzije (npr. video.srt -> video)
    input_path = os.path.join(settings.input_folder, f"{base_name}.srt") # "/app/temp/input" + "moj_film_eng.srt"
    
    # Ensure input directory exists
    os.makedirs(settings.input_folder, exist_ok=True)
    
    # Read file content asynchronously and save
    try:
        content = await file.read()
        with open(input_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    service = OpenAIBatchTranslationService(settings)

    # --- background batch job ---
    background_tasks.add_task(
        service.translate_and_notify,
        input_path=input_path,
        base_name=base_name,
        languages=language_list,
        folder_id=folder_id,
    )

    return {
        "status": "accepted",
        "message": "Batch translation started",
        "languages_count": len(language_list),
    }