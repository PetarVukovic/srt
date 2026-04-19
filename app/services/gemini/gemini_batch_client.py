"""
Gemini Batch Client for Google Gemini Batch API

This module handles interaction with Google Gemini's Batch API for processing
large volumes of translation requests asynchronously.
"""

import json
import time
from typing import Dict, Any
from google import genai
from google.genai import types
from google.genai.errors import ClientError
import asyncio

from app.core.logging import get_logger

logger = get_logger(__name__)

class GeminiBatchClient:
    """
    Client for interacting with Google Gemini's Batch API.
    
    Handles uploading batch files, creating batch jobs, monitoring status,
    and downloading results for subtitle translation tasks.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the Gemini batch client.
        
        Args:
            api_key (str): Google API key for Gemini
        """
        self.client = genai.Client(api_key=api_key)
        
    async def upload_batch_file(self, jsonl_path: str, display_name: str) -> str:
        """
        Upload JSONL batch file to Gemini File API.
        
        Args:
            jsonl_path (str): Path to JSONL file
            display_name (str): Display name for the file
            
        Returns:
            str: Uploaded file name/URI
        """
        logger.info("Uploading Gemini batch file: %s", jsonl_path)
        
        try:
            uploaded_file = self.client.files.upload(
                file=jsonl_path,
                config=types.UploadFileConfig(
                    display_name=display_name,
                    mime_type='jsonl'
                )
            )
            
            logger.info("Gemini batch file uploaded: %s", uploaded_file.name)
            return uploaded_file.name
            
        except Exception as e:
            logger.exception("Failed to upload Gemini batch file: %s", e)
            raise

    async def create_batch_job(self, file_name: str, model: str, display_name: str) -> Dict[str, Any]:
        """
        Create a batch job using uploaded file.
        
        Args:
            file_name (str): Uploaded file name/URI
            model (str): Gemini model to use
            display_name (str): Display name for the batch job
            
        Returns:
            Dict[str, Any]: Batch job information
        """
        logger.info("Creating Gemini batch job: %s", display_name)
        
        try:
            batch_job = self.client.batches.create(
                model=model,
                src=file_name,
                config={
                    'display_name': display_name,
                },
            )
            
            logger.info("Gemini batch job created: %s", batch_job.name)
            return {
                'name': batch_job.name,
                'display_name': batch_job.display_name,
                'state': batch_job.state.name if batch_job.state else None
            }
            
        except ClientError as e:
            if e.status_code == 429:
                logger.warning("Gemini API quota exhausted: %s", e)
                raise RuntimeError(
                    "Gemini API quota exhausted. Please check your quota at "
                    "https://aistudio.google.com/app/apikey and try again later."
                )
            else:
                logger.exception("Failed to create Gemini batch job: %s", e)
                raise
        except Exception as e:
            logger.exception("Failed to create Gemini batch job: %s", e)
            raise

    async def get_batch_status(self, batch_name: str) -> Dict[str, Any]:
        """
        Get the current status of a batch job.
        
        Args:
            batch_name (str): Batch job name
            
        Returns:
            Dict[str, Any]: Current batch status
        """
        try:
            batch_job = self.client.batches.get(name=batch_name)
            
            return {
                'name': batch_job.name,
                'state': batch_job.state.name if batch_job.state else None,
                'display_name': batch_job.display_name,
                'create_time': batch_job.create_time.isoformat() if batch_job.create_time else None,
                'error': str(batch_job.error) if batch_job.error else None
            }
            
        except Exception as e:
            logger.exception("Failed to get Gemini batch status: %s", e)
            raise

    async def wait_until_done(self, batch_name: str, poll_interval: int = 30) -> tuple[str, Dict[str, Any]]:
        """
        Wait for batch job to complete and return results.
        
        Args:
            batch_name (str): Batch job name
            poll_interval (int): Polling interval in seconds
            
        Returns:
            tuple[str, Dict[str, Any]]: (result_file_name, usage_info)
        """
        logger.info("Waiting for Gemini batch completion: %s", batch_name)
        
        completed_states = {
            'JOB_STATE_SUCCEEDED',
            'JOB_STATE_FAILED', 
            'JOB_STATE_CANCELLED',
            'JOB_STATE_EXPIRED'
        }
        
        while True:
            try:
                batch_job = self.client.batches.get(name=batch_name)
                state = batch_job.state.name if batch_job.state else None
                
                logger.info("Gemini batch state | batch=%s | state=%s", batch_name, state)
                
                if state in completed_states:
                    break
                    
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                logger.warning("Error checking Gemini batch status for %s: %s", batch_name, e)
                await asyncio.sleep(poll_interval)
        
        if batch_job.state.name != 'JOB_STATE_SUCCEEDED':
            error_msg = f"Batch failed with state: {batch_job.state.name}"
            if batch_job.error:
                error_msg += f" - {batch_job.error}"
            raise RuntimeError(error_msg)
        
        # Extract usage information
        usage_info = {}
        try:
            # Gemini Batch API usage information
            if hasattr(batch_job, 'usage_metadata') and batch_job.usage_metadata:
                usage_metadata = batch_job.usage_metadata
                usage_info = {
                    'prompt_tokens': getattr(usage_metadata, 'prompt_token_count', 0) or 0,
                    'completion_tokens': getattr(usage_metadata, 'candidates_token_count', 0) or 0,
                    'total_tokens': getattr(usage_metadata, 'total_token_count', 0) or 0,
                }
                logger.info("Gemini token usage | batch=%s | usage=%s", batch_name, usage_info)
            else:
                logger.warning("No usage metadata found in Gemini batch job: %s", batch_name)
                # Try alternative locations for usage info
                if hasattr(batch_job, 'usage') and batch_job.usage:
                    usage = batch_job.usage
                    usage_info = {
                        'prompt_tokens': getattr(usage, 'prompt_tokens', 0) or 0,
                        'completion_tokens': getattr(usage, 'completion_tokens', 0) or 0,
                        'total_tokens': getattr(usage, 'total_tokens', 0) or 0,
                    }
                else:
                    # Default to zero if no usage info found
                    usage_info = {
                        'prompt_tokens': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                    }
        except Exception as e:
            logger.warning("Error extracting Gemini usage info for %s: %s", batch_name, e)
            usage_info = {
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_tokens': 0,
            }
        
        # Get result file name
        result_file_name = None
        if batch_job.dest and hasattr(batch_job.dest, 'file_name'):
            result_file_name = batch_job.dest.file_name
        
        logger.info("Gemini batch completed: %s", batch_job.name)
        return result_file_name, usage_info

    async def download_results(self, file_name: str) -> str:
        """
        Download batch results file.
        
        Args:
            file_name (str): Result file name
            
        Returns:
            str: File content as string
        """
        logger.info("Downloading Gemini batch results: %s", file_name)
        
        try:
            file_content = self.client.files.download(file=file_name)
            content = file_content.decode('utf-8')
            
            logger.info("Gemini batch results downloaded | file=%s | bytes=%s", file_name, len(content))
            return content
            
        except Exception as e:
            logger.exception("Failed to download Gemini batch results %s: %s", file_name, e)
            raise

    async def cancel_batch(self, batch_name: str) -> bool:
        """
        Cancel a running batch job.
        
        Args:
            batch_name (str): Batch job name
            
        Returns:
            bool: True if cancelled successfully
        """
        try:
            self.client.batches.cancel(name=batch_name)
            logger.info("Gemini batch cancelled: %s", batch_name)
            return True
            
        except Exception as e:
            logger.warning("Failed to cancel Gemini batch %s: %s", batch_name, e)
            return False

    async def delete_batch(self, batch_name: str) -> bool:
        """
        Delete a batch job.
        
        Args:
            batch_name (str): Batch job name
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            self.client.batches.delete(name=batch_name)
            logger.info("Gemini batch deleted: %s", batch_name)
            return True
            
        except Exception as e:
            logger.warning("Failed to delete Gemini batch %s: %s", batch_name, e)
            return False
