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
                                        "content": "You are a professional subtitle translator specialized in STRICT, STRUCTURE-PRESERVING translation.\n\n"
                                                "Your task is to translate subtitles into the following target language:\n"
                                                "{language}\n\n"
                                                "You MUST preserve the orig inal sentence structure, word order, repetitions, fillers, pauses, and incomplete or spoken-style phrasing as closely as possible.\n\n"

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

                    f.write(json.dumps(request, ensure_ascii=False) + "\n")

        return output_jsonl