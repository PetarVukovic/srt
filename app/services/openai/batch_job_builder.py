"""
Batch Job Builder for OpenAI Multi-Language Translation

This module builds JSONL batch files for OpenAI's Batch API, enabling
efficient processing of multiple language translations for SRT subtitle files.

The builder creates structured requests that preserve subtitle timing and formatting
while translating content to multiple target languages simultaneously.
"""

import json
import os
import srt
from typing import List, Optional
import chardet

def detect_file_encoding(file_path: str) -> str:
    """
    Detect file encoding using chardet.
    
    Args:
        file_path: Path to the file to analyze
        
    Returns:
        str: Detected encoding (defaults to 'utf-8' if detection fails)
    """
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)  # Read first 10KB for detection
            result = chardet.detect(raw_data)
            encoding = result.get('encoding', 'utf-8')
            confidence = result.get('confidence', 0)
            
            print(f"🔍 Detected encoding: {encoding} (confidence: {confidence:.2f})")
            
            # Fallback to utf-8 if confidence is too low
            if confidence < 0.7:
                print("⚠️ Low confidence, falling back to utf-8")
                return 'utf-8'
                
            return encoding
    except Exception as e:
        print(f"❌ Encoding detection failed: {e}, falling back to utf-8")
        return 'utf-8'

class MultiLangBatchJobBuilder:
    """
    Builds batch job requests for OpenAI's Batch API to translate SRT subtitles.
    
    This class processes SRT subtitle files and creates structured JSONL requests
    that can be submitted to OpenAI's Batch API for efficient multi-language translation.
    
    Attributes:
        model (str): OpenAI model identifier (e.g., 'gpt-4', 'gpt-3.5-turbo')
    """
    
    def __init__(self, model: str):
        """
        Initialize the batch job builder.
        
        Args:
            model (str): OpenAI model to use for translation.
                         Must support chat completions API.
                         Examples: 'gpt-4', 'gpt-3.5-turbo', 'gpt-4-turbo'
        """
        self.model = model

    def build(
        self,
        input_srt: str,
        languages: List[str],
        output_jsonl: str,
        batch_size: int,
    ) -> str:
        """
        Build a multi-language batch job for OpenAI processing.
        
        Args:
            input_srt (str): Path to the input SRT subtitle file
            languages (List[str]): List of target language codes
            output_jsonl (str): Path where the output JSONL file will be saved
            batch_size (int): Number of subtitle entries to include in each request

        Returns:
            str: Path to the generated JSONL file
        """
        # 1. Parse SRT file
        subtitles = self._parse_srt_file(input_srt)
        
        # 2. Process and generate JSONL
        self._generate_batch_requests(subtitles, languages, output_jsonl, batch_size)
        
        return output_jsonl

    def _parse_srt_file(self, input_srt: str) -> List[srt.Subtitle]:
        """
        Parse SRT file with encoding detection and fallback.
        
        Args:
            input_srt (str): Path to SRT file
            
        Returns:
            List[srt.Subtitle]: Parsed subtitle objects
        """
        encoding = detect_file_encoding(input_srt)
        
        try:
            with open(input_srt, "r", encoding=encoding) as f:
                return list(srt.parse(f.read()))
        except UnicodeDecodeError as e:
            print(f" Failed to read with {encoding}: {e}")
            return self._try_fallback_encodings(input_srt)

    def _try_fallback_encodings(self, input_srt: str) -> List[srt.Subtitle]:
        """
        Try multiple encodings as fallback.
        
        Args:
            input_srt (str): Path to SRT file
            
        Returns:
            List[srt.Subtitle]: Parsed subtitle objects
        """
        fallback_encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        
        for enc in fallback_encodings:
            try:
                with open(input_srt, "r", encoding=enc) as f:
                    subtitles = list(srt.parse(f.read()))
                print(f" Successfully read with {enc}")
                return subtitles
            except UnicodeDecodeError:
                continue
                
        raise ValueError(f"Could not read file {input_srt} with any encoding")

    def _generate_batch_requests(self, subtitles: List[srt.Subtitle], languages: List[str], 
                                output_jsonl: str, batch_size: int) -> None:
        """
        Generate JSONL batch requests for all languages and chunks.
        
        Args:
            subtitles (List[srt.Subtitle]): Parsed subtitle objects
            languages (List[str]): Target language codes
            output_jsonl (str): Output JSONL file path
            batch_size (int): Chunk size for processing
        """
        # Safety limit for batch size
        batch_size = min(batch_size, 60)

        with open(output_jsonl, "w", encoding="utf-8") as f:
            for language in languages:
                self._write_language_requests(f, subtitles, language, batch_size)

    def _write_language_requests(self, file_handle, subtitles: List[srt.Subtitle], 
                                language: str, batch_size: int) -> None:
        """
        Write batch requests for a specific language.
        
        Args:
            file_handle: File handle for writing JSONL
            subtitles (List[srt.Subtitle]): Parsed subtitle objects
            language (str): Target language code
            batch_size (int): Chunk size for processing
        """
        for i in range(0, len(subtitles), batch_size):
            chunk = subtitles[i:i + batch_size]
            request = self._create_batch_request(chunk, language, i)
            file_handle.write(json.dumps(request, ensure_ascii=False) + "\n")

    def _create_batch_request(self, chunk: List[srt.Subtitle], language: str, start_index: int) -> dict:
        """
        Create a single batch API request.
        
        Args:
            chunk (List[srt.Subtitle]): Subtitle chunk for this request
            language (str): Target language code
            start_index (int): Starting index of this chunk
            
        Returns:
            dict: Complete API request object
        """
        # Create payload with subtitle indices and content
        payload = [
            {"index": start_index + j, "content": s.content}
            for j, s in enumerate(chunk)
        ]

        # Build complete API request
        return {
            "custom_id": f"{language}:{start_index}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": self._get_system_prompt(language),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
            },
        }

    def _get_system_prompt(self, language: str) -> str:
        """
        Generate system prompt for translation.
        
        Args:
            language (str): Target language code
            
        Returns:
            str: Complete system prompt
        """
        return (
            "You are a professional subtitle translator specialized in STRICT, STRUCTURE-PRESERVING translation.\n\n"
            "Your task is to translate subtitles into the following target language:\n"
            f"{language}\n\n"
            "You MUST preserve the original sentence structure, word order, repetitions, fillers, pauses, and incomplete or spoken-style phrasing as closely as possible.\n\n"

            "INPUT:\n"
            "- A JSON array of subtitle objects\n"
            "- Each object contains 'index' (integer) and 'content' (string)\n\n"

            "OUTPUT:\n"
            "- A JSON array with EXACTLY the same structure.\n"
            "- Each object must contain ONLY:\n"
            "  - 'index' (integer, unchanged)\n"
            "  - 'content' (translated string)\n\n"

            "CRITICAL RULES (MANDATORY):\n"
            "1. Return ONLY a raw JSON array. No markdown, no code fences, no explanations, no extra text.\n"
            "2. The response MUST start with '[' and end with ']'.\n"
            "3. Preserve the EXACT 'index' values from the input.\n"
            "4. DO NOT add, remove, merge, split, or reorder subtitle entries.\n"
            "5. DO NOT summarize, paraphrase, reinterpret, or stylistically improve the text.\n"
            "6. Preserve the ORIGINAL sentence structure, including repetitions, fillers, pauses, and unfinished phrasing.\n"
            "7. If the original sentence is incomplete or interrupted, translate it as incomplete — do NOT complete or smooth it.\n"
            "8. Do NOT introduce explanations, clarifications, or inferred meaning not explicitly present in the source.\n"
            "9. Maintain original line breaks and formatting inside the 'content' field.\n"
            "10. Translate literally and consistently. Prefer accuracy and structural fidelity over fluency.\n\n"

            "ABSOLUTE PROHIBITIONS:\n"
            "- No rephrasing for readability\n"
            "- No stylistic polishing\n"
            "- No removal of repetitions\n"
            "- No normalization of spoken language\n"
            "- No added connectors, conclusions, or inferred intent\n\n"

            "Your goal is MAXIMUM FIDELITY to the original subtitle structure and content, even if the result sounds unnatural.\n\n"

            "Example input:\n"
            "[{\"index\": 0, \"content\": \"Well, you know, this is...\"}]\n\n"
            "Example output:\n"
            "[{\"index\": 0, \"content\": \"Well, you know, this is...\"}]"
        )