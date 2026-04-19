from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, AliasChoices


class Settings(BaseSettings):
    gemini_api_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key")
    )

    gemini_model: str = "gemini-3-flash-preview"
    gemini_temperature: float = 1.0
    gemini_thinking_level: str = "low"

    batch_size: int = 100
    max_batch_files: int = 20
    max_concurrent_files: int = 3

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

    @property
    def reports_folder(self) -> str:
        if self.deployment == "prod":
            return "/opt/render/project/src/app/reports"
        return "./app/reports"

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
