"""
OpenAI Batch Translation Services

This package provides services for translating SRT subtitle files
using OpenAI's Batch API with proper async handling and error management.
"""

# Import individual modules to avoid circular imports
from .openai_batch_translation_service import OpenAIBatchTranslationService
from .batch_job_builder import MultiLangBatchJobBuilder
from .openai_batch_client import OpenAIBatchClient

# Import BatchResultParser if available
try:
    from .batch_result_parser import BatchResultParser
    __all__ = [
        "OpenAIBatchTranslationService",
        "MultiLangBatchJobBuilder", 
        "BatchResultParser",
        "OpenAIBatchClient"
    ]
except ImportError:
    # BatchResultParser not available yet
    __all__ = [
        "OpenAIBatchTranslationService",
        "MultiLangBatchJobBuilder",
        "OpenAIBatchClient"
    ]
