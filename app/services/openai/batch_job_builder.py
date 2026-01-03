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
        
        This method reads an SRT file, splits it into manageable chunks, and creates
        individual translation requests for each chunk in each target language.
        The output is a JSONL file where each line represents a separate API request.
        
        Args:
            input_srt (str): Path to the input SRT subtitle file.
                            Must be UTF-8 encoded and contain valid SRT format.
            
            languages (List[str]): List of target language codes.
                                  Each code should be a 2-3 letter ISO language code
                                  (e.g., 'hr' for Croatian, 'en' for English, 'de' for German).
                                  The service will create translation requests for each language.
            
            output_jsonl (str): Path where the output JSONL file will be saved.
                               This file contains structured requests ready for OpenAI Batch API.
                               Each line is a separate JSON object representing one API request.
            
            batch_size (int): Number of subtitle entries to include in each translation request.
                            Controls the chunk size for processing.
                            Larger batches reduce API calls but may hit token limits.
                            Automatically capped at 60 for safety with multi-language processing.
                            Recommended range: 10-50 depending on subtitle length.

        Returns:
            str: Path to the generated JSONL file (same as output_jsonl parameter).
                 This file can be directly uploaded to OpenAI's Batch API.

        Process:
            1. Parse the SRT file into subtitle objects
            2. Split subtitles into chunks of specified batch_size
            3. For each language and chunk, create a structured API request
            4. Write all requests as JSONL lines to output file

        JSONL Structure:
            Each line contains:
            - custom_id: "{language}:{chunk_start_index}" for tracking
            - method: "POST" for API request
            - url: "/v1/chat/completions" for OpenAI chat completions
            - body: Complete chat completion request with translation instructions

        Example Output Line:
        {
            "custom_id": "hr:0",
            "method": "POST", 
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4",
                "temperature": 0.2,
                "max_tokens": 5000,
                "messages": [...]
            }
        }

        Raises:
            FileNotFoundError: If input_srt file doesn't exist
            srt.SRTParseError: If input file contains invalid SRT format
            OSError: If output_jsonl file cannot be written
        """
        # Parse SRT file into subtitle objects
        encoding = detect_file_encoding(input_srt)
        
        try:
            with open(input_srt, "r", encoding=encoding) as f:
                subtitles = list(srt.parse(f.read()))
        except UnicodeDecodeError as e:
            print(f"❌ Failed to read with {encoding}: {e}")
            # Try common encodings as fallback
            fallback_encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            for enc in fallback_encodings:
                try:
                    with open(input_srt, "r", encoding=enc) as f:
                        subtitles = list(srt.parse(f.read()))
                    print(f"✅ Successfully read with {enc}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not read file {input_srt} with any encoding")

        # Safety limit for batch size in multi-language processing
        # Prevents excessive token usage and API limits
        batch_size = min(batch_size, 60)

        # Generate JSONL file with structured requests
        with open(output_jsonl, "w", encoding="utf-8") as f:
            # Process each target language
            for language in languages:
                # Process subtitle chunks for this language
                for i in range(0, len(subtitles), batch_size):
                    chunk = subtitles[i : i + batch_size]

                    # Create payload with subtitle indices and content
                    payload = [
                        {"index": i + j, "content": s.content}
                        for j, s in enumerate(chunk)
                    ]

                    # Build complete API request
                    request = {
                        "custom_id": f"{language}:{i}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": self.model,
                            "temperature": 0.2,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": "You are a professional subtitle translator specialized in STRICT, STRUCTURE-PRESERVING translation.\n\n"
                                            "Your task is to translate subtitles into the following target language:\n"
                                            "{language}\n\n"
                                            "You MUST preserve the original sentence structure, word order, repetitions, fillers, pauses, and incomplete or spoken-style phrasing as closely as possible.\n\n"

                                            "INPUT:\n"
                                            "- A JSON array of subtitle objects.\n"
                                            "- Each object contains:\n"
                                            "  - 'index' (integer)\n"
                                            "  - 'content' (string)\n\n"

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
                                },
                                {
                                    "role": "user",
                                    "content": json.dumps(payload, ensure_ascii=False),
                                },
                            ],
                        },
                    }

                    # Write request as JSONL line
                    f.write(json.dumps(request, ensure_ascii=False) + "\n")

        return output_jsonl