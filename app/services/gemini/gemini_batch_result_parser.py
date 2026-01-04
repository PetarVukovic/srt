"""
Gemini Batch Result Parser

This module parses and processes results from Google Gemini's Batch API
for subtitle translation tasks.
"""

import json
import srt
import os
from collections import defaultdict
from typing import Dict, List, Any, Optional
from .gemini_batch_builder import detect_file_encoding

class GeminiBatchResultParser:
    """
    Parser for Gemini Batch API results.
    
    Handles parsing of batch output, splitting by language,
    and applying translations to original SRT files.
    """
    
    @staticmethod
    def safe_json_parse(content: str) -> List[Dict[str, Any]]:
        """
        Safely parse JSON returned by Gemini.
        
        Args:
            content (str): JSON content to parse
            
        Returns:
            List[Dict[str, Any]]: Parsed subtitle objects
        """
        if not content:
            raise ValueError("Empty Gemini content")
        
        content = content.strip()
        
        # Try direct JSON parse first
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                return parsed
            else:
                raise ValueError("Expected JSON array")
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        if content.startswith('```json') and content.endswith('```'):
            json_content = content[7:-3].strip()
            try:
                parsed = json.loads(json_content)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # Try to find JSON array in the content
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_content = content[start_idx:end_idx + 1]
            try:
                parsed = json.loads(json_content)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"Could not parse JSON from Gemini response: {content[:200]}...")
    
    @staticmethod
    def split_by_language(batch_output: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Split batch output by language using custom_id format.
        
        Args:
            batch_output (str): Raw batch output JSONL
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: Results grouped by language
        """
        results = defaultdict(list)
        
        lines = batch_output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            try:
                parsed_line = json.loads(line)
                
                # Check if this is a valid response
                if 'response' not in parsed_line or not parsed_line['response']:
                    print(f"⚠️ Skipping line without response")
                    continue
                
                # Extract language and chunk index from key
                key = parsed_line.get('key', '')
                if ':' not in key:
                    print(f"⚠️ Invalid key format: {key}")
                    continue
                
                language, chunk_index = key.split(':', 1)
                
                try:
                    chunk_index = int(chunk_index)
                except ValueError:
                    print(f"⚠️ Invalid chunk index: {chunk_index}")
                    continue
                
                # Parse the response content
                response_content = parsed_line['response']
                if hasattr(response_content, 'text'):
                    content = response_content.text
                elif isinstance(response_content, dict) and 'text' in response_content:
                    content = response_content['text']
                else:
                    content = str(response_content)
                
                # Parse the translated subtitles
                translated_items = GeminiBatchResultParser.safe_json_parse(content)
                
                # Sort by index to maintain order
                translated_items.sort(key=lambda x: x.get('index', 0))
                
                # Add to results
                results[language].extend(translated_items)
                
                print(f"✅ Successfully parsed {len(translated_items)} items for {language}")
                
            except Exception as e:
                print(f"❌ Error parsing line: {e}")
                continue
        
        return dict(results)
    
    @staticmethod
    def apply_translations(
        original_srt: str,
        translated_lines: List[Dict[str, Any]],
        output_srt: str
    ) -> None:
        """
        Apply translations to original SRT file and save.
        
        Args:
            original_srt (str): Path to original SRT file
            translated_lines (List[Dict[str, Any]]): Translated subtitle data
            output_srt (str): Path to save translated SRT file
        """
        if not translated_lines:
            print("⚠️ No translated lines to apply")
            return
        
        # Read original SRT with encoding detection
        encoding = detect_file_encoding(original_srt)
        
        try:
            with open(original_srt, "r", encoding=encoding) as f:
                original_content = f.read()
                original_subtitles = list(srt.parse(original_content))
        except UnicodeDecodeError as e:
            print(f"❌ Failed to read original SRT with {encoding}: {e}")
            # Try fallback encodings
            fallback_encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            for enc in fallback_encodings:
                try:
                    with open(original_srt, "r", encoding=enc) as f:
                        original_content = f.read()
                        original_subtitles = list(srt.parse(original_content))
                    print(f"✅ Successfully read original SRT with {enc}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError(f"Could not read original SRT file {original_srt}")
        
        # Create index mapping for translations
        translation_map = {
            item['index']: item['content'] 
            for item in translated_lines
            if 'index' in item and 'content' in item
        }
        
        # Apply translations to original subtitles
        translated_subtitles = []
        for i, subtitle in enumerate(original_subtitles):
            if i in translation_map:
                # Create new subtitle with translated content
                translated_subtitle = srt.Subtitle(
                    index=subtitle.index,
                    start=subtitle.start,
                    end=subtitle.end,
                    content=translation_map[i]
                )
                translated_subtitles.append(translated_subtitle)
            else:
                # Keep original if no translation found
                translated_subtitles.append(subtitle)
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_srt), exist_ok=True)
        
        # Save translated SRT
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write(srt.compose(translated_subtitles))
        
        print(f"✅ Translations applied and saved to: {output_srt}")
        print(f"📊 Translated {len(translation_map)} out of {len(original_subtitles)} subtitles")
