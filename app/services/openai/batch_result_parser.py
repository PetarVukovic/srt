import json
import srt
import os
from collections import defaultdict

import json
import re
from .batch_job_builder import detect_file_encoding

def safe_json_parse(content: str):
    """
    Safely parses JSON returned by LLM (JSON inside string).
    Returns Python list.
    """
    if not content:
        raise ValueError("Empty LLM content")

    content = content.strip()

    # Remove markdown fences if present
    content = re.sub(r"^```json|```$", "", content, flags=re.MULTILINE).strip()

    # First attempt: direct JSON parse
    try:
        parsed = json.loads(content)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Second attempt: extract JSON array from text
    match = re.search(r"(\[\s*\{.*?\}\s*\])", content, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    raise ValueError("No valid JSON array found in LLM output")


class BatchResultParser:

    @staticmethod
    def split_by_language(batch_output: str):
        results = defaultdict(list)
        errors_by_language = defaultdict(list)

        for line in batch_output.splitlines():
            line = line.strip()
            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON line: {e}")
                continue

            # Skip if record has errors or invalid status
            if record.get("error"):
                # Track errors by language for reporting
                custom_id = record.get("custom_id", "unknown")
                try:
                    lang, chunk_start = custom_id.rsplit(":", 1)
                    errors_by_language[lang].append({
                        "chunk_start": int(chunk_start),
                        "error": record.get("error")
                    })
                except:
                    pass
                print(f"❌ Skipping record with error: {record.get('error')}")
                continue

            # Extract response from record
            response = record.get("response", {})

            # Extract language from custom_id
            try:
                lang, _ = record["custom_id"].rsplit(":", 1)
            except (ValueError, KeyError) as e:
                print(f"❌ Failed to extract language from custom_id: {record.get('custom_id')}")
                continue

            # Extract content from response body
            try:
                content = (
                    response["body"]["choices"][0]["message"]["content"]
                )
            except (KeyError, IndexError, TypeError) as e:
                print(f"❌ Failed to extract content for {lang}: {e}")
                continue

            # Parse translated content
            try:
                parsed = safe_json_parse(content)
                results[lang].extend(parsed)
                print(f"✅ Successfully parsed {len(parsed)} items for {lang}")
            except Exception as e:
                print(f"❌ Failed to parse content for {lang}: {e}")
                continue

        # Report errors
        if errors_by_language:
            print(f"⚠️ Translation errors by language:")
            for lang, errors in errors_by_language.items():
                print(f"   {lang}: {len(errors)} failed chunks")

        print(f"📊 Parsed results for {len(results)} languages: {list(results.keys())}")
        return results

    @staticmethod
    def validate_translation_coverage(translated_lines: list, total_subtitles: int, language: str) -> dict:
        """
        Validate that all subtitle indices are covered by translation.
        
        Returns:
            dict with validation results including missing indices
        """
        translated_indices = set()
        duplicate_indices = []
        
        for item in translated_lines:
            idx = item.get("index")
            if idx is not None:
                if idx in translated_indices:
                    duplicate_indices.append(idx)
                translated_indices.add(idx)
        
        expected_indices = set(range(total_subtitles))
        missing_indices = expected_indices - translated_indices
        extra_indices = translated_indices - expected_indices
        
        coverage_percent = (len(translated_indices & expected_indices) / total_subtitles * 100) if total_subtitles > 0 else 0
        
        validation = {
            "language": language,
            "total_expected": total_subtitles,
            "total_translated": len(translated_indices),
            "coverage_percent": round(coverage_percent, 2),
            "missing_count": len(missing_indices),
            "missing_indices": sorted(list(missing_indices))[:20],  # First 20 for logging
            "duplicate_count": len(duplicate_indices),
            "extra_indices": sorted(list(extra_indices))[:10],
            "is_complete": len(missing_indices) == 0,
        }
        
        if not validation["is_complete"]:
            print(f"⚠️ INCOMPLETE TRANSLATION for {language}:")
            print(f"   Coverage: {coverage_percent:.1f}%")
            print(f"   Missing: {len(missing_indices)} indices")
            print(f"   First missing: {validation['missing_indices'][:10]}")
        else:
            print(f"✅ COMPLETE translation for {language}: {coverage_percent:.1f}% coverage")
        
        return validation

    @staticmethod
    def apply_translations(original_srt: str, translated_lines, output_srt: str, 
                          language: str = "unknown", strict_mode: bool = True):
        """
        Apply translated content to original SRT file.
        
        Args:
            original_srt (str): Path to original SRT file
            translated_lines (list): List of translated subtitle items
            output_srt (str): Path for output SRT file
            language (str): Target language for logging
            strict_mode (bool): If True, raise error on incomplete translation
        """
        print(f"🔧 Applying translations to: {output_srt}")
        print(f"📝 Original SRT: {original_srt}")
        print(f"📊 Translated items: {len(translated_lines)}")
        print(f"🌍 Language: {language}")
        
        # Detect encoding of original file
        encoding = detect_file_encoding(original_srt)
        print(f"🔍 Detected encoding: {encoding}")
        
        try:
            with open(original_srt, encoding="utf-8") as f:
                subtitles = list(srt.parse(f.read()))
            print(f"✅ Successfully read original SRT with UTF-8")
        except UnicodeDecodeError as e:
            print(f"❌ Failed to read original SRT with utf-8: {e}")
            # Try detected encoding first, then fallbacks
            try:
                with open(original_srt, encoding=encoding) as f:
                    subtitles = list(srt.parse(f.read()))
                print(f"✅ Successfully read original SRT with {encoding}")
            except UnicodeDecodeError:
                fallback_encodings = ['utf-16', 'latin-1', 'cp1252']
                for enc in fallback_encodings:
                    try:
                        with open(original_srt, encoding=enc) as f:
                            subtitles = list(srt.parse(f.read()))
                        print(f"✅ Successfully read original SRT with {enc}")
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise ValueError(f"Could not read original SRT file {original_srt}")
        
        print(f"📄 Original subtitles count: {len(subtitles)}")
        
        # Validate translation coverage BEFORE applying
        validation = BatchResultParser.validate_translation_coverage(
            translated_lines, len(subtitles), language
        )
        
        # Check for incomplete translation
        if not validation["is_complete"]:
            warning_msg = (
                f"⚠️ INCOMPLETE TRANSLATION for {language}: "
                f"{validation['coverage_percent']}% coverage, "
                f"{validation['missing_count']} missing indices"
            )
            print(warning_msg)
            
            if strict_mode and validation["coverage_percent"] < 90:
                raise ValueError(
                    f"Translation for {language} is incomplete: "
                    f"only {validation['coverage_percent']}% coverage. "
                    f"Missing {validation['missing_count']} subtitles. "
                    f"This would result in mixed-language output."
                )
        
        # Apply translations
        applied_count = 0
        skipped_count = 0
        
        # Create a map for faster lookup
        translation_map = {}
        for item in translated_lines:
            try:
                idx = item["index"]
                content = item["content"]
                translation_map[idx] = content
            except (KeyError, TypeError):
                continue
        
        # Apply all translations
        for idx in range(len(subtitles)):
            if idx in translation_map:
                subtitles[idx].content = translation_map[idx]
                applied_count += 1
            else:
                # Mark untranslated subtitles (optional - for debugging)
                skipped_count += 1
        
        print(f"✅ Applied {applied_count} translations")
        print(f"⚠️ Skipped {skipped_count} items (kept original)")
        
        # Create output directory
        os.makedirs(os.path.dirname(output_srt), exist_ok=True)
        
        # Write translated SRT
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write(srt.compose(subtitles))
        
        print(f"💾 Saved translated SRT: {output_srt}")
        print(f"📏 Output file size: {os.path.getsize(output_srt)} bytes")
        
        return validation