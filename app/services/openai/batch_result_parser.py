import json
import srt
import os
from collections import defaultdict

import json
import re

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

        print(f"📊 Parsed results for {len(results)} languages: {list(results.keys())}")
        return results
    @staticmethod
    def apply_translations(original_srt: str, translated_lines, output_srt: str):
       with open(original_srt, encoding="utf-8") as f:
           subtitles = list(srt.parse(f.read()))
       for item in translated_lines:
            idx = item["index"]

            if 0 <= idx < len(subtitles):
                subtitles[idx].content = item["content"]
            else:
                print(
                    f"[BatchResultParser] Skipping out-of-range index {idx} "
                    f"(subtitles length = {len(subtitles)})"
                )

       os.makedirs(os.path.dirname(output_srt), exist_ok=True)
       with open(output_srt, "w", encoding="utf-8") as f:
           f.write(srt.compose(subtitles))