"""
OpenAI Batch Translation Service

This module provides a high-level service for translating SRT subtitle files
using OpenAI's Batch API. It handles the complete workflow from file processing
to webhook notifications, making it easy to integrate multi-language subtitle
translation into applications.

The service orchestrates multiple components:
- Batch job building (creating structured API requests)
- OpenAI batch processing (upload, execute, download)
- Result parsing (extracting translated content)
- Pricing calculation (cost tracking)
- Webhook notifications (status updates)

Usage:
    service = OpenAIBatchTranslationService(settings)
    await service.translate_and_notify(
        input_path="subtitles.srt",
        base_name="my_video",
        languages=["hr", "en", "de"],
        folder_id="project_123"
    )
"""

import os
from typing import List, Optional, Dict, Any
from app.services.openai.batch_job_builder import MultiLangBatchJobBuilder
from app.services.openai.openai_batch_client import OpenAIBatchClient
from app.services.webhook import WebhookService
from app.core.config import Settings
from app.services.pricing_calculator import PricingCalculator, Usage

# Import BatchResultParser separately to avoid circular import
try:
    from app.services.openai.batch_result_parser import BatchResultParser
except ImportError:
    # Fallback if module doesn't exist yet
    BatchResultParser = None



# def analyze_batch_output(batch_output: str, temp_folder: str) -> int:
#     """
#     Analyze and log OpenAI batch output for debugging purposes.
    
#     This function creates a detailed analysis file showing the structure
#     and content of batch API responses, useful for debugging translation issues.
    
#     Args:
#         batch_output (str): Raw batch output from OpenAI API.
#                            Contains JSONL formatted responses.
#         temp_folder (str): Path to temporary folder for debug file.
#                           Must exist and be writable.
    
#     Returns:
#         int: Number of lines processed in the batch output.
#              Useful for logging and monitoring.
    
#     Process:
#         1. Create debug analysis file
#         2. Analyze batch output metadata
#         3. Parse each JSON line individually
#         4. Log validation results and content preview
#         5. Save raw output for reference
#     """
#     debug_file = os.path.join(temp_folder, "batch_output_debug.txt")
    
#     with open(debug_file, "w", encoding="utf-8") as f:
#         f.write("=== OPENAI BATCH OUTPUT ANALYSIS ===\n\n")
#         f.write(f"Batch Output Type: {type(batch_output)}\n")
#         f.write(f"Batch Output Length: {len(batch_output)} characters\n\n")
        
#         # Split by lines for analysis
#         lines = batch_output.split('\n')
#         f.write(f"Total Lines: {len(lines)}\n\n")
        
#         # Analyze each line
#         f.write("=== LINE BY LINE ANALYSIS ===\n")
#         valid_json_count = 0
#         invalid_json_count = 0
        
#         for i, line in enumerate(lines):
#             if line.strip():  # Only process non-empty lines
#                 try:
#                     import json
#                     parsed = json.loads(line)
#                     valid_json_count += 1
                    
#                     f.write(f"Line {i+1}: VALID JSON\n")
#                     f.write(f"  - Custom ID: {parsed.get('custom_id', 'N/A')}\n")
#                     f.write(f"  - Status: {parsed.get('response', {}).get('status', 'N/A')}\n")
#                     f.write(f"  - Has content: {'body' in parsed.get('response', {})}\n")
#                     f.write(f"  - Content preview: {str(parsed)[:100]}...\n")
#                     f.write("-" * 50 + "\n")
#                 except json.JSONDecodeError as e:
#                     invalid_json_count += 1
                    
#                     f.write(f"Line {i+1}: INVALID JSON\n")
#                     f.write(f"  - Error: {str(e)}\n")
#                     f.write(f"  - Raw content: {line[:100]}...\n")
#                     f.write("-" * 50 + "\n")
#             else:
#                 f.write(f"Line {i+1}: EMPTY LINE\n")
#                 f.write("-" * 50 + "\n")
        
#         # Summary statistics
#         f.write(f"\n=== SUMMARY ===\n")
#         f.write(f"Valid JSON lines: {valid_json_count}\n")
#         f.write(f"Invalid JSON lines: {invalid_json_count}\n")
#         f.write(f"Empty lines: {len(lines) - valid_json_count - invalid_json_count}\n")
        
#         f.write("\n=== RAW BATCH OUTPUT ===\n")
#         f.write(batch_output)
    
#     print(f"🔍 Debug analysis saved to: {debug_file}")
#     print(f"📊 Batch output contains {len(lines)} lines ({valid_json_count} valid, {invalid_json_count} invalid)")
    
#     return len(lines)


class OpenAIBatchTranslationService:
    """
    High-level service for OpenAI Batch API subtitle translation.
    
    This service manages the complete translation workflow, from building batch jobs
    to processing results and sending notifications. It's designed to be the main
    interface for subtitle translation functionality.
    
    Attributes:
        settings (Settings): Application configuration object containing
                           API keys, file paths, and other settings.
        webhook (WebhookService): Service for sending webhook notifications
                                about translation status and results.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize the translation service.
        
        Args:
            settings (Settings): Application settings object.
                              Must contain:
                              - openai_api_key: OpenAI API key for authentication
                              - openai_model: Model identifier for translation
                              - temp_folder: Path for temporary files
                              - output_folder: Path for generated subtitle files
                              - batch_size: Number of subtitles per API request
        """
        self.settings = settings
        self.webhook = WebhookService(settings)

    async def translate_and_notify(
        self,
        input_path: str,
        base_name: str,
        languages: List[str],
        folder_id: str = None,
    ):
        """
        Translate SRT file and send notification.
        
        Args:
            input_path (str): Path to input SRT file
            base_name (str): Base name for output files
            languages (List[str]): List of target languages
            folder_id (str): Optional folder ID
                             Example: "/path/to/subtitles.srt"
            
            base_name (str): Base name for output files (without extension).
                           Used to generate translated file names.
                           Example: "my_video" → "my_video_hr.srt"
            
            languages (List[str]): List of target language codes.
            
            folder_id (Optional[str]): Optional folder identifier for organization.
                                      Used in webhook payloads and file path organization.

        Returns:
            Dict[str, Any]: Translation results containing:
                - job: Always "srt-translation" (job type identifier)
                - total_languages: Number of languages processed
                - results: List of translation results for each language
                - folder_id: Same as input parameter (for tracking)
                - pricing: Complete pricing information with cost breakdown

        """
        # Check if input file exists at the beginning
        if not os.path.exists(input_path):
            print(f"❌ Input file not found: {input_path}")
            raise FileNotFoundError(f"Input SRT file not found: {input_path}")
        
        print(f"🚀 Starting OpenAI batch translation: {base_name}")
        print(f"🌍 Languages: {languages}")
        print(f"📁 Input: {input_path}")
        
        # 1. Build batch job for OpenAI processing
        builder = MultiLangBatchJobBuilder(
            model=self.settings.openai_model
        )

        # Generate temporary JSONL file path for batch requests
        jsonl_path = os.path.join(
            self.settings.temp_folder,
            "input_batch.jsonl",
        )

        # Create structured batch requests for all languages
        output_jsonl = builder.build(
            input_srt=input_path,
            languages=languages,
            output_jsonl=jsonl_path,
            batch_size=self.settings.batch_size,
        )
        
        # Debug: Save JSONL locally for inspection
        print(f"💾 JSONL saved to: {jsonl_path}")
        print(f"📊 JSONL file size: {os.path.getsize(jsonl_path)} bytes")

        # 2. Execute batch job with OpenAI
        client = OpenAIBatchClient(self.settings.openai_api_key)

        # Upload batch file and create job
        file_id = await client.upload(output_jsonl)
        batch_id = await client.create_batch(file_id)

        print(f"⏳ OpenAI batch started: {batch_id}")

        # Wait for completion and download results
        output_file_id, usage = await client.wait_until_done(batch_id)
        batch_output = await client.download_results(output_file_id)

        # 3. Calculate translation costs
        calculator = PricingCalculator(self.settings.openai_model)

        pricing = calculator.calculate(
            Usage(
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        )
        
        # Debug: Analyze batch output
        #analyze_batch_output(batch_output, self.settings.temp_folder)
        
        results = BatchResultParser.split_by_language(batch_output)

        # Build payload for webhook notification
        bundle_payload = []

        for language, lines in results.items():
            # Generate output file path for this language
            output_srt = os.path.join(
                self.settings.output_folder,
                language,
                f"{base_name}.srt",
            )

            # Check if original file exists
            if not os.path.exists(input_path):
                print(f"❌ Original SRT file not found: {input_path}")
                continue

            # Apply translations to create final SRT file
            BatchResultParser.apply_translations(
                original_srt=input_path,
                translated_lines=lines,
                output_srt=output_srt,
            )

            # Read translated content for webhook payload
            with open(output_srt, "r", encoding="utf-8") as f:
                content = f.read()

            # Add result for this language
            bundle_payload.append({
                "language": language,
                "filename": f"{language}/{base_name}.srt",
                "content": content,
                "folder_id": folder_id,
                "pricing": pricing,
            })

        # 5. Send webhook notification with complete results
        self.webhook.send({
            "job": "srt-translation",
            "total_languages": len(bundle_payload),
            "results": bundle_payload,
            "folder_id": folder_id,
            "pricing": pricing,
        })

        print("✅ Batch done & webhook(s) sent")


        if not self.settings.deployment == "local":
            os.unlink(input_path)
            os.unlink(output_jsonl)
        
        return {
            "job": "srt-translation",
            "total_languages": len(bundle_payload),
            "results": bundle_payload,
            "folder_id": folder_id,
            "pricing": pricing,
        }