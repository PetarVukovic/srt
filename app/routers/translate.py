"""Translation API endpoints."""

import os
import tempfile
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, HTTPException
from app.core.config import (
    Settings,
    get_settings,
    TARGET_LANGUAGES,
)
from app.services.openai import OpenAIBatchTranslationService
from app.services.gemini import GeminiBatchTranslationService

router = APIRouter(prefix="/batch/translate", tags=["translate"])

def cleanup_file(file_path: str) -> None:
    """Safely remove file if it exists."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            print(f"🗑️ Cleaned up: {file_path}")
    except Exception as e:
        print(f"⚠️ Failed to cleanup {file_path}: {e}")

def cleanup_batch_files(base_name: str, settings: Settings) -> None:
    """Clean up batch-related files."""
    # Clean up input SRT file
    input_path = os.path.join(settings.input_folder, f"{base_name}.srt")
    cleanup_file(input_path)
    
    # Clean up batch JSONL files
    batch_jsonl = os.path.join(settings.temp_folder, f"{base_name}_batch.jsonl")
    cleanup_file(batch_jsonl)
    
    gemini_jsonl = os.path.join(settings.temp_folder, f"{base_name}_gemini_batch.jsonl")
    cleanup_file(gemini_jsonl)
    
    # Clean up OpenAI output JSONL
    output_jsonl = os.path.join(settings.temp_folder, "output_batch.jsonl")
    cleanup_file(output_jsonl)


@router.post("/batch-translate-srt")
async def batch_translate_srt(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] | UploadFile = File(...),
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    provider: Optional[str] = Form("openai"),  # openai or gemini
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

    # --- select service provider ---
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise HTTPException(
                status_code=400,
                detail="Gemini API key not configured. Please set GEMINI_API_KEY environment variable or use provider=openai"
            )
        service = GeminiBatchTranslationService(settings)
    else:
        service = OpenAIBatchTranslationService(settings)

    accepted_files = []

    if isinstance(files, list):
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
            
            # Add cleanup task (runs after translation completes)
            background_tasks.add_task(
                cleanup_batch_files,
                base_name=base_name,
                settings=settings,
            )

            accepted_files.append(file.filename)
    # Handle single file case
    else:
        file = files  # files is already a single UploadFile
        if file.filename.lower().endswith(".srt"):
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

            background_tasks.add_task(
                service.translate_and_notify,
                input_path=input_path,
                base_name=base_name,
                languages=language_list,
                folder_id=folder_id,
            )
            
            # Add cleanup task (runs after translation completes)
            background_tasks.add_task(
                cleanup_batch_files,
                base_name=base_name,
                settings=settings,
            )

            accepted_files.append(file.filename)


    return {
        "status": "accepted",
        "provider": provider,
        "files_count": len(accepted_files),
        "files": accepted_files,
        "languages_count": len(language_list),
        "message": "Batch translation jobs scheduled",
    }


@router.post("/batch-translate-srt-gemini")
async def batch_translate_srt_gemini(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] | UploadFile = File(...),
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
):
    """Dedicated Gemini batch translation endpoint."""
    return await batch_translate_srt(
        background_tasks=background_tasks,
        files=files,
        languages=languages,
        folder_id=folder_id,
        provider="gemini"
    )