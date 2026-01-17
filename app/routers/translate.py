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
    MAX_FILES = 5  # Maksimalno 5 fajlova odjednom

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

    # --- validate file count ---
    if isinstance(files, list):
        if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum {MAX_FILES} files allowed per request. You uploaded {len(files)} files."
            )
    # Single file case - wrap in list for uniform processing
    else:
        files = [files]

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
    failed_files = []

    # --- process each file ---
    for file in files:
        if not file.filename.lower().endswith(".srt"):
            failed_files.append({
                "filename": file.filename,
                "error": "Only .srt files are supported"
            })
            continue

        base_name = os.path.splitext(file.filename)[0]
        input_path = os.path.join(settings.input_folder, f"{base_name}.srt")

        try:
            # Save uploaded file
            content = await file.read()
            with open(input_path, "wb") as f:
                f.write(content)

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
            print(f"✅ Scheduled translation for: {file.filename}")

        except Exception as e:
            error_msg = f"Failed to save uploaded file {file.filename}: {str(e)}"
            print(f"❌ {error_msg}")
            failed_files.append({
                "filename": file.filename,
                "error": str(e)
            })

    # --- return comprehensive response ---
    response = {
        "status": "accepted",
        "provider": provider,
        "files_count": len(accepted_files),
        "accepted_files": accepted_files,
        "failed_files": failed_files,
        "languages_count": len(language_list),
        "languages": language_list,
        "message": f"Scheduled {len(accepted_files)} translation jobs",
    }

    if failed_files:
        response["warning"] = f"{len(failed_files)} files failed to process"

    return response


@router.post("/batch-translate-multiple")
async def batch_translate_multiple(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., max_length=5),  # Max 5 files
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    provider: Optional[str] = Form("openai"),  # openai or gemini
    max_concurrent: int = Form(3),  # Max concurrent translations
):
    """
    Advanced endpoint for multiple SRT files with concurrent processing.
    
    - Max 5 files per request
    - Concurrent processing (max 3 at a time)
    - Detailed error reporting
    - Progress tracking
    """
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

    # --- validate and save files ---
    file_configs = []
    accepted_files = []
    failed_files = []

    for file in files:
        if not file.filename.lower().endswith(".srt"):
            failed_files.append({
                "filename": file.filename,
                "error": "Only .srt files are supported"
            })
            continue

        base_name = os.path.splitext(file.filename)[0]
        input_path = os.path.join(settings.input_folder, f"{base_name}.srt")

        try:
            # Save uploaded file
            content = await file.read()
            with open(input_path, "wb") as f:
                f.write(content)

            file_configs.append({
                "input_path": input_path,
                "base_name": base_name,
                "languages": language_list,
            })

            accepted_files.append(file.filename)
            print(f"✅ Prepared file for processing: {file.filename}")

        except Exception as e:
            error_msg = f"Failed to save uploaded file {file.filename}: {str(e)}"
            print(f"❌ {error_msg}")
            failed_files.append({
                "filename": file.filename,
                "error": str(e)
            })

    if not file_configs:
        raise HTTPException(
            status_code=400,
            detail="No valid SRT files were provided for processing"
        )

    # --- enqueue concurrent batch processing ---
    if provider == "openai" and hasattr(service, 'translate_multiple_files'):
        # Use concurrent processing for OpenAI
        background_tasks.add_task(
            service.translate_multiple_files,
            file_configs=file_configs,
            folder_id=folder_id,
            max_concurrent=max_concurrent,
        )
        
        # Add cleanup for all files
        for config in file_configs:
            background_tasks.add_task(
                cleanup_batch_files,
                base_name=config["base_name"],
                settings=settings,
            )
    else:
        # Fallback to individual processing for Gemini or if method not available
        for config in file_configs:
            background_tasks.add_task(
                service.translate_and_notify,
                input_path=config["input_path"],
                base_name=config["base_name"],
                languages=config["languages"],
                folder_id=folder_id,
            )
            
            background_tasks.add_task(
                cleanup_batch_files,
                base_name=config["base_name"],
                settings=settings,
            )

    # --- return comprehensive response ---
    response = {
        "status": "accepted",
        "provider": provider,
        "processing_mode": "concurrent" if provider == "openai" else "sequential",
        "files_count": len(accepted_files),
        "accepted_files": accepted_files,
        "failed_files": failed_files,
        "languages_count": len(language_list),
        "languages": language_list,
        "max_concurrent": max_concurrent,
        "message": f"Scheduled {len(accepted_files)} files for concurrent translation",
    }

    if failed_files:
        response["warning"] = f"{len(failed_files)} files failed to process"

    return response


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