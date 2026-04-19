"""Translation API endpoints."""

import os
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile, HTTPException

from app.core.config import Settings, TARGET_LANGUAGES, get_settings
from app.core.logging import get_logger
from app.services.gemini import GeminiBatchTranslationService

router = APIRouter(prefix="/batch/translate", tags=["translate"])
logger = get_logger(__name__)


def cleanup_file(file_path: str) -> None:
    """Safely remove file if it exists."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info("Cleaned up file: %s", file_path)
    except Exception as e:
        logger.warning("Failed to cleanup file %s: %s", file_path, e)


def cleanup_batch_files(base_name: str, settings: Settings) -> None:
    """Clean up batch-related files."""
    input_path = os.path.join(settings.input_folder, f"{base_name}.srt")
    cleanup_file(input_path)

    gemini_jsonl = os.path.join(settings.temp_folder, f"{base_name}_gemini_batch.jsonl")
    cleanup_file(gemini_jsonl)


def parse_languages(languages: Optional[str]) -> List[str]:
    """Parse requested languages or fallback to default language list."""
    if not languages:
        return TARGET_LANGUAGES
    return [lang.strip() for lang in languages.split(",") if lang.strip()]


def ensure_runtime_directories(settings: Settings) -> None:
    """Create runtime directories used by the service if they do not exist."""
    os.makedirs(settings.input_folder, exist_ok=True)
    os.makedirs(settings.output_folder, exist_ok=True)
    os.makedirs(settings.temp_folder, exist_ok=True)
    os.makedirs(settings.reports_folder, exist_ok=True)


def get_translation_service(settings: Settings) -> GeminiBatchTranslationService:
    """Validate configuration and create the Gemini translation service."""
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=400,
            detail="Gemini API key not configured. Please set GEMINI_API_KEY environment variable.",
        )
    return GeminiBatchTranslationService(settings)


def validate_files_count(files: List[UploadFile], max_files: int) -> None:
    """Validate number of uploaded files."""
    if len(files) > max_files:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_files} files allowed per request. You uploaded {len(files)} files.",
        )


async def save_uploaded_srt_files(
    files: List[UploadFile],
    settings: Settings,
    languages: List[str],
) -> tuple[List[dict], List[str], List[dict]]:
    """Persist uploaded SRT files and build translation job configs."""
    file_configs: List[dict] = []
    accepted_files: List[str] = []
    failed_files: List[dict] = []

    for file in files:
        if not file.filename or not file.filename.lower().endswith(".srt"):
            failed_files.append(
                {
                    "filename": file.filename or "",
                    "error": "Only .srt files are supported",
                }
            )
            continue

        base_name = os.path.splitext(file.filename)[0]
        input_path = os.path.join(settings.input_folder, f"{base_name}.srt")

        try:
            content = await file.read()
            with open(input_path, "wb") as f:
                f.write(content)

            file_configs.append(
                {
                    "input_path": input_path,
                    "base_name": base_name,
                    "languages": languages,
                }
            )
            accepted_files.append(file.filename)
            logger.info("Prepared file for processing: %s", file.filename)
        except Exception as e:
            failed_files.append(
                {
                    "filename": file.filename,
                    "error": f"Failed to save uploaded file: {e}",
                }
            )

    return file_configs, accepted_files, failed_files


@router.post("/srt")
async def batch_translate_srt(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] | UploadFile = File(...),
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
):
    """Schedule translation jobs for one or more SRT files."""
    settings: Settings = get_settings()
    max_files = settings.max_batch_files
    file_list = files if isinstance(files, list) else [files]
    validate_files_count(file_list, max_files)
    language_list = parse_languages(languages)
    ensure_runtime_directories(settings)
    service = get_translation_service(settings)

    file_configs, accepted_files, failed_files = await save_uploaded_srt_files(
        files=file_list,
        settings=settings,
        languages=language_list,
    )

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

    response = {
        "status": "accepted",
        "provider": "gemini",
        "files_count": len(accepted_files),
        "max_files": max_files,
        "accepted_files": accepted_files,
        "failed_files": failed_files,
        "languages_count": len(language_list),
        "languages": language_list,
        "message": f"Scheduled {len(accepted_files)} translation jobs",
    }

    if failed_files:
        response["warning"] = f"{len(failed_files)} files failed to process"

    return response


@router.post("/multiple")
async def batch_translate_multiple(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    languages: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    max_concurrent: int = Form(3),  # Max concurrent translations
):
    """
    Schedule concurrent translation for multiple SRT files.
    """
    settings: Settings = get_settings()
    max_files = settings.max_batch_files
    max_concurrent = max(1, min(max_concurrent, settings.max_concurrent_files))
    validate_files_count(files, max_files)
    language_list = parse_languages(languages)
    ensure_runtime_directories(settings)
    service = get_translation_service(settings)

    file_configs, accepted_files, failed_files = await save_uploaded_srt_files(
        files=files,
        settings=settings,
        languages=language_list,
    )

    if not file_configs:
        raise HTTPException(
            status_code=400,
            detail="No valid SRT files were provided for processing",
        )

    if hasattr(service, "translate_multiple_files"):
        background_tasks.add_task(
            service.translate_multiple_files,
            file_configs=file_configs,
            folder_id=folder_id,
            max_concurrent=max_concurrent,
        )

        for config in file_configs:
            background_tasks.add_task(
                cleanup_batch_files,
                base_name=config["base_name"],
                settings=settings,
            )
    else:
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
        "provider": "gemini",
        "processing_mode": "concurrent" if hasattr(service, "translate_multiple_files") else "sequential",
        "files_count": len(accepted_files),
        "max_files": max_files,
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
