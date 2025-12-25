"""Translation API endpoints."""

import os
import shutil
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import (
    Settings,
    get_settings,
    TARGET_LANGUAGES,
)
from app.services.openai_batch_translation_service import (
    OpenAIBatchTranslationService,
)

router = APIRouter()


@router.post("/translate-srt")
async def translate_srt(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    notify_mode: str = Form("per_language"),  # per_language | bundle
    languages: Optional[str] = Form(None),    # "English,Spanish,French"
    folder_id: Optional[str] = Form(None),
):
    settings: Settings = get_settings()

    # --- validate notify mode ---
    if notify_mode not in {"per_language", "bundle"}:
        return JSONResponse(
            status_code=400,
            content={"error": "notify_mode must be 'per_language' or 'bundle'"},
        )

    # --- parse languages ---
    if languages:
        language_list = [
            lang.strip()
            for lang in languages.split(",")
            if lang.strip()
        ]
        if not language_list:
            return JSONResponse(
                status_code=400,
                content={"error": "languages parameter is empty"},
            )
    else:
        language_list = TARGET_LANGUAGES

    # --- save input file ---
    input_path = os.path.join(settings.input_folder, file.filename)
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    base_name = os.path.splitext(file.filename)[0]

    service = OpenAIBatchTranslationService(settings)

    # --- background batch job ---
    background_tasks.add_task(
        service.translate_and_notify,
        input_path=input_path,
        base_name=base_name,
        languages=language_list,
        notify_mode=notify_mode,
        folder_id=folder_id,
    )

    return {
        "status": "accepted",
        "message": "Batch translation started",
        "notify_mode": notify_mode,
        "languages_count": len(language_list),
        "languages": language_list,
    }