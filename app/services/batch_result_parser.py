import json
import srt
import os
from collections import defaultdict


class BatchResultParser:

    @staticmethod
    def split_by_language(batch_output: str):
        results = defaultdict(list)
        for line in batch_output.splitlines():
            record = json.loads(line)
            if record["error"]:
                continue
            lang, _ = record["custom_id"].split(":")
            content = record["response"]["body"]["choices"][0]["message"]["content"]
            results[lang].extend(json.loads(content))
        return results

    @staticmethod
    def apply_translations(original_srt: str, translated_lines, output_srt: str):
        subtitles = list(srt.parse(open(original_srt, encoding="utf-8").read()))
        for item in translated_lines:
            subtitles[item["index"]].content = item["content"]

        os.makedirs(os.path.dirname(output_srt), exist_ok=True)
        with open(output_srt, "w", encoding="utf-8") as f:
            f.write(srt.compose(subtitles))