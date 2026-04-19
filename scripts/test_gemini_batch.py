#!/usr/bin/env python3
"""
Mali smoke-test za Gemini Batch:
1) generira kratki SRT
2) napravi JSONL batch input
3) uploada file i kreira batch job
4) ispiše batch ID i trenutno stanje
"""

import argparse
import asyncio
import os
import sys
import textwrap
from pathlib import Path


# Omogući `import app...` kad se skripta pokreće iz /scripts
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.gemini import GeminiBatchTranslationService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini Batch smoke-test")
    parser.add_argument(
        "--language",
        default="Croatian",
        help="Ciljni jezik za test (default: Croatian)",
    )
    parser.add_argument(
        "--base-name",
        default="smoke_test_short",
        help="Bazno ime za test fajlove (default: smoke_test_short)",
    )
    return parser.parse_args()


def build_test_srt(path: str) -> None:
    content = textwrap.dedent(
        """\
        1
        00:00:01,000 --> 00:00:03,000
        Hello world!

        2
        00:00:03,500 --> 00:00:05,000
        This is a short batch test.
        """
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + "\n")


async def run() -> int:
    args = parse_args()
    settings = get_settings()

    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY nije postavljen (.env).")
        return 1

    service = GeminiBatchTranslationService(settings)
    os.makedirs(settings.input_folder, exist_ok=True)
    os.makedirs(settings.temp_folder, exist_ok=True)

    input_path = os.path.join(settings.input_folder, f"{args.base_name}.srt")
    jsonl_path = os.path.join(settings.temp_folder, f"{args.base_name}.jsonl")

    build_test_srt(input_path)

    service.builder.build(
        input_srt=input_path,
        languages=[args.language],
        output_jsonl=jsonl_path,
        batch_size=20,
    )

    uploaded_file = await service.client.upload_batch_file(
        jsonl_path=jsonl_path,
        display_name=f"{args.base_name}_batch_input",
    )

    batch = await service.client.create_batch_job(
        file_name=uploaded_file,
        model=settings.gemini_model,
        display_name=f"{args.base_name}_batch_job",
    )

    status = await service.client.get_batch_status(batch["name"])

    print(f"OK: batch created")
    print(f"batch_name: {batch['name']}")
    print(f"state: {status['state']}")
    print(f"input_srt: {input_path}")
    print(f"jsonl: {jsonl_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
