# app/services/openai_batch_translation_service.py

import os
from app.services.batch_job_builder import MultiLangBatchJobBuilder
from app.services.batch_result_parser import BatchResultParser
from app.services.openai_batch_client import OpenAIBatchClient
from app.services.webhook import WebhookService
from app.core.config import Settings
from typing import Optional
from app.services.pricing_calculator import PricingCalculator, Usage

class OpenAIBatchTranslationService:

    def __init__(self, settings:Settings):
        self.settings = settings
        self.webhook = WebhookService(settings)

    def translate_and_notify(
        self,
        input_path: str,
        base_name: str,
        languages: list[str],
        folder_id: Optional[str] = None,
        notify_mode: str = "per_language",  # or "bundle"
    ):
        # 1. Build batch
        builder = MultiLangBatchJobBuilder(
            model=self.settings.openai_model
        )

        jsonl_path = os.path.join(
            self.settings.temp_folder,
            "openai_multilang_batch.jsonl",
        )

        builder.build(
            input_srt=input_path,
            languages=languages,
            output_jsonl=jsonl_path,
            batch_size=self.settings.batch_size,
        )

        # 2. Run batch
        client = OpenAIBatchClient(self.settings.openai_api_key)

        file_id = client.upload(jsonl_path)
        batch_id = client.create_batch(file_id)

        print(f"⏳ OpenAI batch started: {batch_id}")

        output_file_id, usage = client.wait_until_done(batch_id)
        batch_output = client.download_results(output_file_id)


        calculator = PricingCalculator(self.settings.openai_model)

        batch_usage = usage  # ovo je BatchUsage objekt

        pricing = calculator.calculate(
            Usage(
                prompt_tokens=batch_usage.get("input_tokens", 0),
                completion_tokens=batch_usage.get("output_tokens", 0),
                total_tokens=batch_usage.get("total_tokens", 0),
            )
        )

        # 3. Parse
        results = BatchResultParser.split_by_language(batch_output)

        bundle_payload = []

        for language, lines in results.items():
            output_srt = os.path.join(
                self.settings.output_folder,
                language,
                f"{base_name}.srt",
            )

            BatchResultParser.apply_translations(
                original_srt=input_path,
                translated_lines=lines,
                output_srt=output_srt,
            )

            with open(output_srt, "r", encoding="utf-8") as f:
                content = f.read()

            if notify_mode == "per_language":
                self.webhook.send({
                    "language": language,
                    "filename": f"{language}/{base_name}.srt",
                    "status": "ok",
                    "content": content,
                    "folder_id": folder_id,
                    "pricing": pricing,
                })

            else:  # bundle
                bundle_payload.append({
                    "language": language,
                    "filename": f"{language}/{base_name}.srt",
                    "content": content,
                    "folder_id": folder_id,
                    "pricing": pricing,
                })

        if notify_mode == "bundle":
            self.webhook.send({
                "job": "srt-translation",
                "total_languages": len(bundle_payload),
                "results": bundle_payload,
                "folder_id": folder_id,
                "pricing": pricing,
            })

        print("✅ Batch done & webhook(s) sent")