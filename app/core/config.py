import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field,SecretStr,AliasChoices,PostgresDsn


class Settings(BaseSettings):
    openai_api_key: SecretStr = Field(
        ...,
       validation_alias=AliasChoices("OPENAI_API_KEY","openai_api_key")
    )

    openai_model: str = "gpt-4.1-mini"

    n8n_webhook_url: str = Field(
        ...,
        validation_alias=AliasChoices("N8N_WEBHOOK_URL", "N8N"),
    )

    batch_size: int = 100

    database_url: PostgresDsn = Field(
        ...,
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }



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
