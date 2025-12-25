import time
from openai import OpenAI


class OpenAIBatchClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def upload(self, jsonl_path: str) -> str:
        return self.client.files.create(
            file=open(jsonl_path, "rb"),
            purpose="batch",
        ).id

    def create_batch(self, file_id: str) -> str:
        return self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        ).id

    def wait_until_done(self, batch_id: str) -> str:
        while True:
            batch = self.client.batches.retrieve(batch_id)
            if batch.status == "completed":
                return batch.output_file_id
            time.sleep(15)

    def download_results(self, file_id: str) -> str:
        return self.client.files.content(file_id).text