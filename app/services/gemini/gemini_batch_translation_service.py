"""
Gemini Batch Translation Service

This module provides the main service for translating SRT subtitle files
using Google Gemini's Batch API with multi-language support.
"""

import asyncio
import json
import os
import srt
from typing import List, Dict, Any

from app.core.logging import get_logger
from .gemini_batch_builder import GeminiBatchJobBuilder, detect_file_encoding
from .gemini_batch_client import GeminiBatchClient
from .gemini_batch_result_parser import GeminiBatchResultParser
from app.core.config import Settings
from app.services.local_report_store import LocalReportStore
from app.services.srt_merge_preprocessor import SRTMergePreprocessor

logger = get_logger(__name__)

GEMINI_BATCH_PRICING_PER_MILLION = {
    "gemini-3-flash-preview": {
        "input": 0.25,
        "output": 1.50,
        "pricing_mode": "batch",
    },
}


class GeminiBatchTranslationService:
    """
    Service for translating SRT files using Google Gemini Batch API.
    
    Handles the complete workflow:
    1. Build batch requests from SRT file
    2. Upload and create batch job
    3. Monitor completion
    4. Parse and apply translations
    5. Save translated files
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the translation service.
        
        Args:
            settings (Settings): Application settings
        """
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key is required. Please set GEMINI_API_KEY environment variable.")
        
        self.settings = settings
        self.client = GeminiBatchClient(settings.gemini_api_key)
        self.builder = GeminiBatchJobBuilder(
            model=settings.gemini_model,
            temperature=settings.gemini_temperature,
            thinking_level=settings.gemini_thinking_level,
        )
        self.preprocessor = SRTMergePreprocessor()
        self.report_store = LocalReportStore(settings)

    async def translate_multiple_files(
        self,
        file_configs: List[Dict[str, Any]],
        folder_id: str = None,
        max_concurrent: int = 3,
    ) -> Dict[str, Any]:
        """
        Translate multiple SRT files concurrently with a bounded concurrency limit.
        """
        logger.info(
            "Starting Gemini multi-file translation | files=%s | max_concurrent=%s",
            len(file_configs),
            max_concurrent,
        )
        semaphore = asyncio.Semaphore(max(1, max_concurrent))

        async def translate_single_with_limit(config: Dict[str, Any]) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.translate_and_notify(
                        input_path=config["input_path"],
                        base_name=config["base_name"],
                        languages=config["languages"],
                        folder_id=folder_id,
                    )
                except Exception as e:
                    logger.exception("Failed to translate file %s: %s", config["base_name"], e)
                    return {
                        "job": "srt-translation",
                        "base_name": config["base_name"],
                        "status": "failed",
                        "error": str(e),
                        "translated_files": [],
                        "pricing": {"total_cost": 0},
                    }

        tasks = [translate_single_with_limit(config) for config in file_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = [r for r in results if isinstance(r, dict) and r.get("status") != "failed"]
        failed = [r for r in results if isinstance(r, dict) and r.get("status") == "failed"]
        exceptions = [str(r) for r in results if not isinstance(r, dict)]
        total_cost = sum(r.get("pricing", {}).get("total_cost", 0) for r in successful)

        combined_results = {
            "job": "multi-file-translation",
            "provider": "gemini",
            "total_files": len(file_configs),
            "successful_files": len(successful),
            "failed_files": len(failed),
            "exceptions": exceptions,
            "successful_results": successful,
            "failed_results": failed,
            "total_cost": total_cost,
            "folder_id": folder_id,
            "request_group": folder_id or "default",
        }

        logger.info(
            "Gemini multi-file translation completed | successful=%s | failed=%s | exceptions=%s | total_cost=%s",
            len(successful),
            len(failed),
            len(exceptions),
            round(total_cost, 6),
        )
        return combined_results
        
    async def translate_and_notify(
        self,
        input_path: str,
        base_name: str,
        languages: List[str],
        folder_id: str = None,
    ) -> Dict[str, Any]:
        """
        Translate SRT file using Gemini Batch API and send notification.
        
        Args:
            input_path (str): Path to input SRT file
            base_name (str): Base name for output files
            languages (List[str]): List of target languages
            folder_id (str): Optional folder ID
        """
        # Check if input file exists at the beginning
        if not os.path.exists(input_path):
            logger.error("Input SRT file not found: %s", input_path)
            raise FileNotFoundError(f"Input SRT file not found: {input_path}")
        
        logger.info(
            "Starting Gemini batch translation | base_name=%s | languages=%s | input=%s",
            base_name,
            languages,
            input_path,
        )

        try:
            preprocess_result = self.preprocessor.preprocess_file(input_path)
            logger.info(
                "Preprocessed SRT | base_name=%s | original=%s | merged=%s | deleted=%s",
                base_name,
                preprocess_result["original_segments"],
                preprocess_result["merged_segments"],
                preprocess_result["deleted_segments"],
            )

            input_encoding = detect_file_encoding(input_path)
            with open(input_path, "r", encoding=input_encoding) as f:
                total_subtitles = len(list(srt.parse(f.read())))

            # 1. Build batch requests
            jsonl_path = os.path.join(
                self.settings.temp_folder, 
                f"{base_name}_gemini_batch.jsonl"
            )
            
            logger.info("Building Gemini batch requests | base_name=%s", base_name)
            self.builder.build(
                input_srt=input_path,
                languages=languages,
                output_jsonl=jsonl_path,
                batch_size=self.settings.batch_size
            )
            
            # Check file size and log
            file_size = os.path.getsize(jsonl_path)
            logger.info("Gemini JSONL saved | path=%s | bytes=%s", jsonl_path, file_size)
            
            # 2. Upload batch file
            file_display_name = f"{base_name}_batch_requests"
            uploaded_file_name = await self.client.upload_batch_file(
                jsonl_path, file_display_name
            )
            
            # 3. Create batch job
            batch_display_name = f"{base_name}_translation_{len(languages)}_langs"
            batch_info = await self.client.create_batch_job(
                file_name=uploaded_file_name,
                model=self.settings.gemini_model,
                display_name=batch_display_name
            )
            
            batch_name = batch_info['name']
            logger.info("Gemini batch started | batch_name=%s", batch_name)
            
            # 4. Wait for completion
            result_file_name, usage = await self.client.wait_until_done(batch_name)
            
            # 5. Download results
            if result_file_name:
                batch_output = await self.client.download_results(result_file_name)
            else:
                raise RuntimeError("No result file returned from batch job")
            
            # 6. Debug: Analyze batch output
            self._analyze_batch_output(batch_output, self.settings.temp_folder)
            
            # 7. Parse results by language
            results = GeminiBatchResultParser.split_by_language(batch_output)
            logger.info(
                "Parsed Gemini batch results | languages_count=%s | languages=%s",
                len(results),
                list(results.keys()),
            )

            # 8. Apply translations and save files
            translated_files = []
            validation_results = []
            for language, lines in results.items():
                validation = GeminiBatchResultParser.validate_translation_coverage(
                    translated_lines=lines,
                    total_subtitles=total_subtitles,
                    language=language,
                )
                validation_results.append(validation)

                if not validation["is_complete"]:
                    logger.warning(
                        "Rejecting incomplete translation | language=%s | coverage=%s | missing=%s",
                        language,
                        validation["coverage_percent"],
                        validation["missing_count"],
                    )
                    continue

                # Create output directory
                request_group = folder_id or "default"
                output_dir = os.path.join(self.settings.output_folder, request_group, language)
                os.makedirs(output_dir, exist_ok=True)
                
                # Generate output file path
                output_srt = os.path.join(output_dir, f"{base_name}.srt")
                
                # Apply translations
                GeminiBatchResultParser.apply_translations(
                    original_srt=input_path,
                    translated_lines=lines,
                    output_srt=output_srt
                )
                
                translated_files.append({
                    "language": language,
                    "file_path": output_srt,
                    "lines_count": len(lines),
                    "validation": validation,
                })
                
                logger.info("Translation saved | language=%s | path=%s", language, output_srt)
            
            # 9. Calculate pricing
            pricing = self._calculate_pricing(usage)
            
            # 10. Prepare result
            result = {
                "status": "completed",
                "provider": "gemini",
                "batch_name": batch_name,
                "input_file": input_path,
                "base_name": base_name,
                "languages": languages,
                "translated_files": translated_files,
                "preprocess": preprocess_result,
                "request_group": folder_id or "default",
                "validation_summary": {
                    "total_languages": len(languages),
                    "complete_count": len(translated_files),
                    "incomplete_count": len([v for v in validation_results if not v["is_complete"]]),
                    "incomplete_languages": [v["language"] for v in validation_results if not v["is_complete"]],
                    "all_complete": len(translated_files) == len(languages),
                },
                "usage": usage,
                "pricing": pricing,
                "folder_id": folder_id
            }

            result["report_csv_path"] = self.report_store.write_request_report(result)
            
            logger.info("Gemini batch finished and translations applied | base_name=%s", base_name)
            return result
            
        except Exception as e:
            logger.exception("Gemini translation failed | base_name=%s | error=%s", base_name, e)
            
            # Check if it's quota exhaustion and provide Gemini-specific guidance
            if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                raise RuntimeError(
                    f"Gemini quota exhausted. {e}\n"
                    "To continue translating, please:\n"
                    "1. Check your Gemini quota at https://aistudio.google.com/app/apikey\n"
                    "2. Wait for quota reset (usually daily)\n"
                    "3. Retry the request after quota is available again"
                )
            else:
                raise
    
    def _analyze_batch_output(self, batch_output: str, temp_folder: str) -> None:
        """
        Analyze batch output for debugging.
        
        Args:
            batch_output (str): Raw batch output
            temp_folder (str): Temporary folder path
        """
        debug_file = os.path.join(temp_folder, "gemini_batch_output_debug.txt")
        
        try:
            lines = batch_output.strip().split('\n')
            valid_count = 0
            invalid_count = 0
            
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"=== Gemini Batch Output Analysis ===\n")
                f.write(f"Total lines: {len(lines)}\n\n")
                
                for i, line in enumerate(lines):
                    if not line.strip():
                        continue
                        
                    try:
                        parsed = json.loads(line)
                        if 'response' in parsed and parsed['response']:
                            valid_count += 1
                            f.write(f"Line {i+1}: ✅ Valid response\n")
                        else:
                            invalid_count += 1
                            f.write(f"Line {i+1}: ❌ Invalid/No response\n")
                            f.write(f"Content: {line[:200]}...\n\n")
                    except json.JSONDecodeError:
                        invalid_count += 1
                        f.write(f"Line {i+1}: ❌ JSON decode error\n")
                        f.write(f"Content: {line[:200]}...\n\n")
                
                f.write(f"\n=== Summary ===\n")
                f.write(f"Valid responses: {valid_count}\n")
                f.write(f"Invalid responses: {invalid_count}\n")
            
            logger.info(
                "Gemini batch debug analysis saved | path=%s | total_lines=%s | valid=%s | invalid=%s",
                debug_file,
                len(lines),
                valid_count,
                invalid_count,
            )
            
        except Exception as e:
            logger.warning("Failed to analyze Gemini batch output: %s", e)
    
    def _calculate_pricing(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate translation costs based on usage.
        
        Args:
            usage (Dict[str, Any]): Token usage information
            
        Returns:
            Dict[str, Any]: Pricing details
        """
        pricing = GEMINI_BATCH_PRICING_PER_MILLION.get(self.settings.gemini_model)
        if pricing is None:
            raise ValueError(
                f"No batch pricing configured for Gemini model '{self.settings.gemini_model}'."
            )

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        total_cost = input_cost + output_cost

        return {
            "model": self.settings.gemini_model,
            "pricing_mode": pricing["pricing_mode"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "currency": "USD",
            "rates_per_million_tokens": {
                "input": pricing["input"],
                "output": pricing["output"],
            },
        }
