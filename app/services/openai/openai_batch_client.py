import asyncio
import time
from openai import AsyncOpenAI


class OpenAIBatchClient:
    """
    Client for interacting with OpenAI's Batch API.
    
    This class provides methods to upload batch files, create batch jobs,
    monitor their progress, and download results. It uses the async OpenAI client
    for efficient processing.
    
    Attributes:
        client (AsyncOpenAI): Async OpenAI client instance.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the OpenAI batch client.
        
        Args:
            api_key (str): OpenAI API key for authentication.
        """
        self.client = AsyncOpenAI(api_key=api_key)

    async def upload(self, jsonl_path: str) -> str:
        """
        Upload JSONL file to OpenAI for batch processing.
        
        Args:
            jsonl_path (str): Path to the JSONL file to upload.
                            File must contain properly formatted batch requests.
                            
        Returns:
            str: OpenAI file ID for the uploaded file.
                 Used to create batch jobs.
                 
        Raises:
            FileNotFoundError: If jsonl_path doesn't exist.
            OpenAIError: If upload fails due to API issues.
        """
        with open(jsonl_path, "rb") as file:
            response = await self.client.files.create(
                file=file,
                purpose="batch",
            )
        return response.id

    async def create_batch(self, file_id: str) -> str:
        """
        Create a batch job from uploaded file.
        
        Args:
            file_id (str): OpenAI file ID returned from upload().
                         Must be a file with purpose="batch".
                         
        Returns:
            str: OpenAI batch ID for monitoring the job.
                 Used to check status and retrieve results.
                 
        Raises:
            OpenAIError: If batch creation fails.
        """
        response = await self.client.batches.create(
            input_file_id=file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )
        return response.id

    async def wait_until_done(self, batch_id: str) -> tuple[str, dict]:
        """
        Wait for batch job to complete and return results.
        
        This method polls the batch status every 60 seconds until completion.
        Only returns when status is "completed".
        
        Args:
            batch_id (str): OpenAI batch ID from create_batch().
                          Used to monitor job progress.
                          
        Returns:
            tuple[str, dict]: Contains:
                - output_file_id (str): File ID containing results
                - usage (dict): Token usage statistics with keys:
                    - input_tokens: Input tokens used
                    - output_tokens: Output tokens generated  
                    - total_tokens: Total tokens processed
                    
        Raises:
            OpenAIError: If batch fails or is cancelled.
            TimeoutError: If batch takes too long (no explicit timeout).
        """
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
            await asyncio.sleep(60)

    async def download_results(self, file_id: str) -> str:
        """
        Download batch results from OpenAI.
        
        Args:
            file_id (str): Output file ID from wait_until_done().
                         Contains completed batch results.
                         
        Returns:
            str: Raw JSONL content with translation results.
                 Each line contains a separate API response.
                 
        Raises:
            OpenAIError: If download fails or file not found.
        """
        response = await self.client.files.content(file_id)
        return response.text