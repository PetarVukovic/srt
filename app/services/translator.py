"""Translation service using Gemini SRT Translator."""

import signal
import time
from typing import Dict, Any

from gemini_srt_translator.main import GeminiSRTTranslator

from app.core.config import Settings


class SignalPatcher:
    """Context manager for safely patching signal handlers in background threads."""
    
    def __init__(self, language: str):
        self.language = language
        self.original_signal = None
        self.original_raise_signal = None
    
    def __enter__(self):
        self.original_signal = signal.signal
        self.original_raise_signal = getattr(signal, 'raise_signal', None)
        
        language = self.language
        original_signal = self.original_signal
        original_raise_signal = self.original_raise_signal
        
        def safe_signal(sig, handler):
            try:
                return original_signal(sig, handler)
            except ValueError as e:
                if "signal only works in main thread" in str(e):
                    print(f"⚠️ Ignoring signal setup in background thread for {language}")
                    return None
                raise
        
        def safe_raise_signal(sig):
            try:
                if original_raise_signal:
                    return original_raise_signal(sig)
            except ValueError as e:
                if "signal only works in main thread" in str(e):
                    print(f"⚠️ Ignoring signal raise in background thread for {language}")
                    return None
                raise
        
        signal.signal = safe_signal
        if original_raise_signal:
            signal.raise_signal = safe_raise_signal
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.signal = self.original_signal
        if self.original_raise_signal:
            signal.raise_signal = self.original_raise_signal
        return False


class TranslatorService:
    """Service for translating SRT files."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def translate(
        self,
        input_path: str,
        output_path: str,
        language: str,
        api_key: str,
    ) -> Dict[str, Any]:
        """
        Translate an SRT file to a target language.
        
        Args:
            input_path: Path to input SRT file
            output_path: Path for output translated file
            language: Target language
            api_key: Gemini API key to use
            
        Returns:
            Dictionary with translation result
        """
        try:
            start_time = time.time()
            
            translator = GeminiSRTTranslator(
                gemini_api_key=api_key,
                target_language=language,
                input_file=input_path,
                output_file=output_path,
                free_quota=self.settings.free_quota,
                use_colors=False,
                resume=True,
                batch_size=self.settings.batch_size,
            )
            
            with SignalPatcher(language):
                translator.translate()
            
            duration = round(time.time() - start_time)
            
            return {
                "language": language,
                "status": "success",
                "duration": duration,
                "output_path": output_path,
            }
            
        except Exception as e:
            return {
                "language": language,
                "status": "error",
                "error": str(e),
                "output_path": output_path,
            }
