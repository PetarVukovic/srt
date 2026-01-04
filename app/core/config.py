import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field,SecretStr,AliasChoices,PostgresDsn


class Settings(BaseSettings):
    openai_api_key: str = Field(
        ...,
       validation_alias=AliasChoices("OPENAI_API_KEY","openai_api_key")
    )

    openai_model: str = "gpt-4.1-mini"

    gemini_api_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key")
    )

    gemini_model: str = "gemini-2.5-flash"

    n8n_webhook_url: str = Field(
        ...,
        validation_alias=AliasChoices("N8N_WEBHOOK_URL", "N8N"),
    )

    batch_size: int = 100

    # Paths - different for local vs production
    @property
    def input_folder(self) -> str:
        if self.deployment == "prod":
            return "/opt/render/project/src/app/srt_input"
        return "./app/srt_input"
    
    @property  
    def output_folder(self) -> str:
        if self.deployment == "prod":
            return "/opt/render/project/src/app/batch_output"
        return "./app/batch_output"
    
    @property
    def temp_folder(self) -> str:
        if self.deployment == "prod":
            return "/opt/render/project/src/app/batch_inputs"
        return "./app/batch_inputs"

    # database_url: PostgresDsn = Field(
    #     ...,
    #     validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    # )

    deployment:str = Field(
        "local",
        validation_alias=AliasChoices("DEPLOYMENT", "deployment"),
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }



def get_settings() -> Settings:
    return Settings()


TARGET_LANGUAGES: List[str] = [
     "English",
    "Mandarin Chinese",
    "Hindi",
    "Spanish",
    "Arabic",
    "Bengali",
    "Portuguese",
    "Russian",
    "Urdu",
    "Indonesian",
    "Standard German",
    "Japanese",
    "Swahili",
    "Marathi",
    "Telugu",
    "Turkish",
    "French",
    "Vietnamese",
    "Korean",
    "Tamil",
    "Yue Chinese (Cantonese)",
    "Italian",
    "Thai",
    "Gujarati",
    "Javanese",
    "Polish",
    "Western Punjabi",
    "Ukrainian",
    "Persian (Farsi)",
    "Malayalam",
    "Slovenian",
    "Serbian (on Српски!)",
    "Macedonian (on Македонски!)",
]
