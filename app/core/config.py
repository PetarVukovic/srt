import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-4.1-mini"

    # Webhook
    n8n_webhook_url: str

    # Folders
    input_folder: str = "srt-files"
    output_folder: str = "srt-prijevodi"
    temp_folder: str = "tmp"

    # Translation
    batch_size: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


TARGET_LANGUAGES: List[str] = [
     "English",
    # # "Mandarin Chinese",
    # # "Hindi",
    # # "Spanish",
    # # "Arabic",
    # # "Bengali",
    # # "Portuguese",
    # # "Russian",
    # # "Urdu",
    # # "Indonesian",
    # "Standard German",
    # "Japanese",
    # "Swahili",
    # "Marathi",
    # "Telugu",
    # "Turkish",
    # "French",
    # "Vietnamese",
    # "Korean",
    # "Tamil",
    # "Yue Chinese (Cantonese)",
    # "Italian",
    # "Thai",
    # "Gujarati",
    # "Javanese",
    # "Polish",
    # "Western Punjabi",
    # "Ukrainian",
    # "Persian (Farsi)",
    # "Malayalam",
    # "Slovenian",
    # "Serbian (on Српски!)",
    # "Macedonian (on Македонски!)",
]


def setup_folders(settings: Settings):
    os.makedirs(settings.input_folder, exist_ok=True)
    os.makedirs(settings.output_folder, exist_ok=True)
    os.makedirs(settings.temp_folder, exist_ok=True)