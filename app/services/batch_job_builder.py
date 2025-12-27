# app/services/batch_job_builder.py

import json
import srt


class MultiLangBatchJobBuilder:
    """Builds a batch job for multiple languages."""
    def __init__(self, model: str):
        self.model = model

    def build(
        self,
        input_srt: str,
        languages: list[str],
        output_jsonl: str,
        batch_size: int,
    ) -> str:
        """Builds a batch job for multiple languages."""
        subtitles = list(
            srt.parse(open(input_srt, encoding="utf-8").read())
        )

        # 🔒 sigurni batch size za multilang
        batch_size = min(batch_size, 60)

        with open(output_jsonl, "w", encoding="utf-8") as f:
            #Iteration over languages
            for language in languages:
                #Iteration over chunks of srt file for that language and creating batch items
                for i in range(0, len(subtitles), batch_size):
                    chunk = subtitles[i : i + batch_size]

                    payload = [
                        {"index": i + j, "content": s.content}
                        for j, s in enumerate(chunk)
                    ] #lista dictova koja sadrzi index i chunck srt fila

                    request = {
                        "custom_id": f"{language}:{i}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": self.model,
                            "temperature": 0.2,
                            "max_tokens": 5000,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a professional subtitle translator.\n"
                                        f"Translate ALL subtitles to {language}.\n\n"
                                        "STRICT OUTPUT RULES:\n"
                                        "- Return ONLY a valid JSON array\n"
                                        "- Each item must have: index (int), content (string)\n"
                                        "- Do NOT include explanations, comments, markdown, or extra text\n"
                                        "- The response MUST start with '[' and end with ']'\n"
                                        "- Preserve the original index values exactly\n"
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": json.dumps(payload, ensure_ascii=False),
                                },
                            ],
                        },
                    }

                    f.write(json.dumps(request, ensure_ascii=False) + "\n")

        return output_jsonl