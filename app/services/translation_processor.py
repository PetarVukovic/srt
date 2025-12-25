import os
from app.services.openai_batch_translation_service import OpenAIBatchTranslationService


class TranslationProcessor:
    def __init__(self, settings):
        self.settings = settings
        self.openai_batch_service = OpenAIBatchTranslationService(settings)

    def process_openai_batch_translations(self, input_path, base_name, languages):
        print(f"🚀 OpenAI Batch → {len(languages)} languages")
        self.openai_batch_service.translate_many_languages(
            input_path, base_name, languages
        )
        os.remove(input_path)