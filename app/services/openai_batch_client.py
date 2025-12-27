import time
from openai import AsyncOpenAI


class OpenAIBatchClient:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    async def upload(self, jsonl_path: str) -> str:
        response = await self.client.files.create(
            file=open(jsonl_path, "rb"),
            purpose="batch",
        )
        return response.id

    async def create_batch(self, file_id: str) -> str:
        response = await self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )
        return response.id

    async def wait_until_done(self, batch_id: str) -> tuple[str, dict]:
        while True:
            batch = await self.client.batches.retrieve(batch_id)
            if batch.status == "completed":
                usage = {}
                if batch.usage:
                    usage = {
                        "input_tokens": batch.usage.input_tokens,
                        "output_tokens": batch.usage.output_tokens,
                        "total_tokens": batch.usage.total_tokens,
                    }
                return batch.output_file_id, usage
            time.sleep(15)

    async def download_results(self, file_id: str) -> str:
        response = await self.client.files.content(file_id)
        return response.text