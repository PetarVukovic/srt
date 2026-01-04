"""
Gemini Batch Translation Service

This module provides the main service for translating SRT subtitle files
using Google Gemini's Batch API with multi-language support.
"""

import json
import os
from typing import List, Dict, Any
from .gemini_batch_builder import GeminiBatchJobBuilder
from .gemini_batch_client import GeminiBatchClient
from .gemini_batch_result_parser import GeminiBatchResultParser
from app.core.config import Settings

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
        self.builder = GeminiBatchJobBuilder(settings.gemini_model)
        
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
            print(f"❌ Input file not found: {input_path}")
            raise FileNotFoundError(f"Input SRT file not found: {input_path}")
        
        print(f"🚀 Starting Gemini batch translation: {base_name}")
        print(f"🌍 Languages: {languages}")
        print(f"📁 Input: {input_path}")
        
        try:
            # 1. Build batch requests
            jsonl_path = os.path.join(
                self.settings.temp_folder, 
                f"{base_name}_gemini_batch.jsonl"
            )
            
            print(f"🔨 Building batch requests...")
            self.builder.build(
                input_srt=input_path,
                languages=languages,
                output_jsonl=jsonl_path,
                batch_size=60
            )
            
            # Check file size and log
            file_size = os.path.getsize(jsonl_path)
            print(f"💾 JSONL saved to: {jsonl_path}")
            print(f"📊 JSONL file size: {file_size} bytes")
            
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
            print(f"⏳ Gemini batch started: {batch_name}")
            
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
            print(f"📊 Parsed results for {len(results)} languages: {list(results.keys())}")
            
            # 8. Apply translations and save files
            translated_files = []
            for language, lines in results.items():
                # Create output directory
                output_dir = os.path.join(self.settings.output_folder, language)
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
                    "lines_count": len(lines)
                })
                
                print(f"✅ Translation saved: {output_srt}")
            
            # 9. Calculate pricing
            pricing = self._calculate_pricing(usage)
            
            # 10. Prepare result
            result = {
                "status": "completed",
                "batch_name": batch_name,
                "input_file": input_path,
                "base_name": base_name,
                "languages": languages,
                "translated_files": translated_files,
                "usage": usage,
                "pricing": pricing,
                "folder_id": folder_id
            }
            
            print(f"✅ Batch done & translations applied")
            return result
            
        except Exception as e:
            print(f"❌ Gemini translation failed: {e}")
            
            # Check if it's quota exhaustion and suggest OpenAI fallback
            if "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                print("💡 Suggestion: Try using OpenAI provider instead")
                print("   Set provider: openai in your request")
                raise RuntimeError(
                    f"Gemini quota exhausted. {e}\n"
                    "To continue translating, please:\n"
                    "1. Check your Gemini quota at https://aistudio.google.com/app/apikey\n"
                    "2. Wait for quota reset (usually daily)\n"
                    "3. Or use OpenAI provider by setting provider=openai"
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
            
            print(f"🔍 Debug analysis saved to: {debug_file}")
            print(f"📊 Batch output contains {len(lines)} lines ({valid_count} valid, {invalid_count} invalid)")
            
        except Exception as e:
            print(f"❌ Failed to analyze batch output: {e}")
    
    def _calculate_pricing(self, usage: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate translation costs based on usage.
        
        Args:
            usage (Dict[str, Any]): Token usage information
            
        Returns:
            Dict[str, Any]: Pricing details
        """
        # Gemini pricing (example rates - adjust based on actual pricing)
        # These are placeholder rates - update with actual Gemini pricing
        input_cost_per_1k = 0.000125  # $0.125 per 1M input tokens
        output_cost_per_1k = 0.000375  # $0.375 per 1M output tokens
        
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)
        total_tokens = usage.get('total_tokens', 0)
        
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "input_cost": round(input_cost, 6),
            "output_cost": round(output_cost, 6),
            "total_cost": round(total_cost, 6),
            "currency": "USD"
        }
