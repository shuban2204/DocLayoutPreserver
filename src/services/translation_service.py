"""Translation Service component for translating text via Gemini API."""

import time
import logging
from typing import List, Optional
from dataclasses import dataclass

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions


logger = logging.getLogger(__name__)


@dataclass
class TranslationRequest:
    """Request for translating a text block."""
    text: str
    source_lang: Optional[str]
    target_lang: str
    block_id: str


@dataclass
class TranslationResult:
    """Result of a translation operation."""
    original_text: str
    translated_text: str
    block_id: str
    success: bool
    error_message: Optional[str] = None


class TranslationError(Exception):
    """Exception raised when translation fails."""
    pass


class TranslationService:
    """Manages translation via Gemini API with batch processing and retry logic."""

    MAX_RETRIES: int = 3
    INITIAL_DELAY: float = 0.5
    MAX_DELAY: float = 10.0
    BATCH_SIZE: int = 50  # Increased from 10 for faster processing

    def __init__(
        self, 
        api_key: str, 
        target_lang: str,
        source_lang: Optional[str] = None,
        model_name: str = "gemini-2.5-pro"
    ):
        """
        Initialize with Gemini API credentials.
        
        Args:
            api_key: Gemini API key
            target_lang: Target language for translation
            source_lang: Source language (auto-detected if None)
            model_name: Gemini model to use
        """
        self._api_key = api_key
        self._target_lang = target_lang
        self._source_lang = source_lang
        self._model_name = model_name
        self._model = None
        self._initialized = False

    def _initialize(self) -> None:
        """Initialize the Gemini API client."""
        if self._initialized:
            return
        
        try:
            genai.configure(api_key=self._api_key)
            self._model = genai.GenerativeModel(self._model_name)
            self._initialized = True
        except Exception as e:
            raise TranslationError(f"Failed to initialize Gemini API: {str(e)}")

    def set_source_language(self, source_lang: str) -> None:
        """
        Set the source language for translation.
        
        Args:
            source_lang: Source language code
        """
        self._source_lang = source_lang

    def translate_batch(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """
        Translate multiple text blocks in batched API calls.
        
        Args:
            requests: List of TranslationRequest objects
            
        Returns:
            List of TranslationResult objects
        """
        self._initialize()
        
        if not requests:
            return []
        
        results: List[TranslationResult] = []
        
        # Process in batches
        for i in range(0, len(requests), self.BATCH_SIZE):
            batch = requests[i:i + self.BATCH_SIZE]
            batch_results = self._translate_batch_internal(batch)
            results.extend(batch_results)
        
        return results

    def _translate_batch_internal(self, requests: List[TranslationRequest]) -> List[TranslationResult]:
        """
        Translate a batch of requests in a single API call.
        
        Args:
            requests: Batch of TranslationRequest objects
            
        Returns:
            List of TranslationResult objects
        """
        if not requests:
            return []
        
        # Build prompt for batch translation
        texts = [req.text for req in requests]
        source_lang = requests[0].source_lang or self._source_lang or "auto-detect"
        
        try:
            translated_texts = self._call_gemini_api(texts, self._target_lang, source_lang)
            
            # Match results to requests
            results = []
            for i, req in enumerate(requests):
                if i < len(translated_texts):
                    results.append(TranslationResult(
                        original_text=req.text,
                        translated_text=translated_texts[i],
                        block_id=req.block_id,
                        success=True,
                    ))
                else:
                    # Fallback if translation missing
                    results.append(TranslationResult(
                        original_text=req.text,
                        translated_text=req.text,
                        block_id=req.block_id,
                        success=False,
                        error_message="Translation not returned",
                    ))
            
            return results
            
        except Exception as e:
            # Return original text with error flag for all requests
            logger.error(f"Batch translation failed: {str(e)}")
            return [
                TranslationResult(
                    original_text=req.text,
                    translated_text=req.text,
                    block_id=req.block_id,
                    success=False,
                    error_message=str(e),
                )
                for req in requests
            ]

    def _call_gemini_api(
        self, 
        texts: List[str], 
        target_lang: str,
        source_lang: str = "auto-detect"
    ) -> List[str]:
        """
        Call Gemini API with retry logic.
        
        Args:
            texts: List of texts to translate
            target_lang: Target language
            source_lang: Source language
            
        Returns:
            List of translated texts
        """
        prompt = self._build_translation_prompt(texts, target_lang, source_lang)
        
        delay = self.INITIAL_DELAY
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                response = self._model.generate_content(prompt)
                
                if not response.text:
                    raise TranslationError("Empty response from Gemini API")
                
                # Parse response
                translated_texts = self._parse_translation_response(response.text, len(texts))
                return translated_texts
                
            except (google_exceptions.ResourceExhausted, 
                    google_exceptions.ServiceUnavailable,
                    google_exceptions.DeadlineExceeded) as e:
                # Retryable errors
                last_error = e
                logger.warning(f"Gemini API error (attempt {attempt + 1}): {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, self.MAX_DELAY)
                    
            except google_exceptions.InvalidArgument as e:
                # Non-retryable error
                raise TranslationError(f"Invalid request: {str(e)}")
                
            except Exception as e:
                last_error = e
                logger.warning(f"Translation error (attempt {attempt + 1}): {str(e)}")
                
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, self.MAX_DELAY)
        
        # All retries failed
        raise TranslationError(f"Translation failed after {self.MAX_RETRIES} attempts: {str(last_error)}")

    def _build_translation_prompt(
        self, 
        texts: List[str], 
        target_lang: str,
        source_lang: str
    ) -> str:
        """
        Build the translation prompt for Gemini.
        
        Args:
            texts: List of texts to translate
            target_lang: Target language
            source_lang: Source language
            
        Returns:
            Formatted prompt string
        """
        # Number each text for parsing
        numbered_texts = "\n".join(
            f"[{i+1}] {text}" 
            for i, text in enumerate(texts)
        )
        
        source_instruction = f"from {source_lang}" if source_lang != "auto-detect" else ""
        
        prompt = f"""Translate the following texts {source_instruction} to {target_lang}.

IMPORTANT RULES:
1. Preserve any formatting markers, special characters, numbers, and punctuation
2. Keep the same numbering format [1], [2], etc. in your response
3. Translate ONLY the text content, not the numbers in brackets
4. If a text is already in the target language, return it unchanged
5. Maintain the original meaning and tone

Texts to translate:
{numbered_texts}

Respond with ONLY the translations in the same numbered format:
[1] <translation>
[2] <translation>
..."""

        return prompt

    def _parse_translation_response(self, response: str, expected_count: int) -> List[str]:
        """
        Parse the translation response from Gemini.
        
        Args:
            response: Raw response text
            expected_count: Expected number of translations
            
        Returns:
            List of translated texts
        """
        translations: List[str] = [""] * expected_count
        lines = response.strip().split("\n")
        
        current_index = -1
        current_translation = ""
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with [number]
            import re
            match = re.match(r'^\[(\d+)\]\s*(.*)', line)
            if match:
                # Save previous translation if exists
                if current_index >= 0 and current_index < expected_count:
                    translations[current_index] = current_translation.strip()
                
                # Extract new translation
                current_index = int(match.group(1)) - 1  # Convert to 0-indexed
                current_translation = match.group(2)
            else:
                # Continuation of previous translation
                if current_index >= 0:
                    current_translation += " " + line
        
        # Add last translation
        if current_index >= 0 and current_index < expected_count:
            translations[current_index] = current_translation.strip()
        
        return translations

    def translate_single(self, text: str, block_id: str = "single") -> TranslationResult:
        """
        Translate a single text block.
        
        Args:
            text: Text to translate
            block_id: Identifier for the text block
            
        Returns:
            TranslationResult object
        """
        request = TranslationRequest(
            text=text,
            source_lang=self._source_lang,
            target_lang=self._target_lang,
            block_id=block_id,
        )
        
        results = self.translate_batch([request])
        return results[0] if results else TranslationResult(
            original_text=text,
            translated_text=text,
            block_id=block_id,
            success=False,
            error_message="Translation failed",
        )
