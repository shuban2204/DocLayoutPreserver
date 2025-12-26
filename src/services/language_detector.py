"""Language Detector component for automatic source language detection."""

from typing import List, Tuple, Optional
from collections import Counter

from langdetect import detect, detect_langs, LangDetectException
from langdetect.lang_detect_exception import ErrorCode

from models.data_models import TextBlock, LanguageDetectionResult


class LanguageDetectionError(Exception):
    """Exception raised when language detection fails."""
    pass


class LanguageDetector:
    """Automatically detects the source language of document text."""

    CONFIDENCE_THRESHOLD: float = 0.7
    MIN_TEXT_LENGTH: int = 20  # Minimum characters for reliable detection
    MAX_SAMPLES: int = 10  # Maximum text blocks to sample

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Initialize the language detector.
        
        Args:
            confidence_threshold: Minimum confidence for reliable detection
        """
        self.confidence_threshold = confidence_threshold

    def detect_language(self, text_blocks: List[TextBlock]) -> LanguageDetectionResult:
        """
        Detect language from multiple text blocks.
        
        Samples text from multiple pages/blocks for accuracy.
        
        Args:
            text_blocks: List of TextBlock objects to analyze
            
        Returns:
            LanguageDetectionResult with primary and secondary languages
        """
        if not text_blocks:
            return LanguageDetectionResult(
                primary_language="unknown",
                confidence=0.0,
                secondary_languages=[],
                sample_size=0,
            )
        
        # Sample text from blocks
        sampled_text = self._sample_text(text_blocks, self.MAX_SAMPLES)
        
        if len(sampled_text) < self.MIN_TEXT_LENGTH:
            return LanguageDetectionResult(
                primary_language="unknown",
                confidence=0.0,
                secondary_languages=[],
                sample_size=len(sampled_text),
            )
        
        try:
            # Detect languages with probabilities
            detected_langs = detect_langs(sampled_text)
            
            if not detected_langs:
                return LanguageDetectionResult(
                    primary_language="unknown",
                    confidence=0.0,
                    secondary_languages=[],
                    sample_size=len(sampled_text),
                )
            
            # Primary language is the one with highest probability
            primary = detected_langs[0]
            primary_language = primary.lang
            confidence = primary.prob
            
            # Secondary languages
            secondary_languages: List[Tuple[str, float]] = [
                (lang.lang, lang.prob) 
                for lang in detected_langs[1:]
                if lang.prob > 0.1  # Only include if > 10% probability
            ]
            
            return LanguageDetectionResult(
                primary_language=primary_language,
                confidence=confidence,
                secondary_languages=secondary_languages,
                sample_size=len(sampled_text),
            )
            
        except LangDetectException as e:
            # Handle specific langdetect errors
            if e.code == ErrorCode.CantDetectError:
                return LanguageDetectionResult(
                    primary_language="unknown",
                    confidence=0.0,
                    secondary_languages=[],
                    sample_size=len(sampled_text),
                )
            raise LanguageDetectionError(f"Language detection failed: {str(e)}")
        except Exception as e:
            raise LanguageDetectionError(f"Language detection failed: {str(e)}")

    def _sample_text(self, text_blocks: List[TextBlock], max_samples: int = 10) -> str:
        """
        Sample text from blocks for detection.
        
        Samples from different pages for better accuracy.
        
        Args:
            text_blocks: List of text blocks to sample from
            max_samples: Maximum number of blocks to sample
            
        Returns:
            Combined sampled text
        """
        if not text_blocks:
            return ""
        
        # Group blocks by page
        pages: dict = {}
        for block in text_blocks:
            page_num = block.page_number
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(block)
        
        # Sample evenly from different pages
        sampled_blocks: List[TextBlock] = []
        page_numbers = sorted(pages.keys())
        
        # Calculate samples per page
        samples_per_page = max(1, max_samples // len(page_numbers))
        
        for page_num in page_numbers:
            page_blocks = pages[page_num]
            # Sort by text length (prefer longer blocks for better detection)
            page_blocks_sorted = sorted(
                page_blocks, 
                key=lambda b: len(b.text), 
                reverse=True
            )
            # Take top blocks from this page
            sampled_blocks.extend(page_blocks_sorted[:samples_per_page])
            
            if len(sampled_blocks) >= max_samples:
                break
        
        # Combine text from sampled blocks
        texts = [block.text for block in sampled_blocks[:max_samples]]
        return " ".join(texts)

    def detect_from_text(self, text: str) -> LanguageDetectionResult:
        """
        Detect language from raw text string.
        
        Args:
            text: Text string to analyze
            
        Returns:
            LanguageDetectionResult
        """
        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return LanguageDetectionResult(
                primary_language="unknown",
                confidence=0.0,
                secondary_languages=[],
                sample_size=len(text) if text else 0,
            )
        
        try:
            detected_langs = detect_langs(text)
            
            if not detected_langs:
                return LanguageDetectionResult(
                    primary_language="unknown",
                    confidence=0.0,
                    secondary_languages=[],
                    sample_size=len(text),
                )
            
            primary = detected_langs[0]
            secondary_languages = [
                (lang.lang, lang.prob) 
                for lang in detected_langs[1:]
                if lang.prob > 0.1
            ]
            
            return LanguageDetectionResult(
                primary_language=primary.lang,
                confidence=primary.prob,
                secondary_languages=secondary_languages,
                sample_size=len(text),
            )
            
        except LangDetectException:
            return LanguageDetectionResult(
                primary_language="unknown",
                confidence=0.0,
                secondary_languages=[],
                sample_size=len(text),
            )

    def is_confident(self, result: LanguageDetectionResult) -> bool:
        """
        Check if the detection result meets the confidence threshold.
        
        Args:
            result: LanguageDetectionResult to check
            
        Returns:
            True if confidence is above threshold
        """
        return (
            result.primary_language != "unknown" and
            result.confidence >= self.confidence_threshold
        )

    def get_language_name(self, lang_code: str) -> str:
        """
        Get human-readable language name from ISO 639-1 code.
        
        Args:
            lang_code: Two-letter language code
            
        Returns:
            Human-readable language name
        """
        language_names = {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "ru": "Russian",
            "zh-cn": "Chinese (Simplified)",
            "zh-tw": "Chinese (Traditional)",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "hi": "Hindi",
            "nl": "Dutch",
            "pl": "Polish",
            "tr": "Turkish",
            "vi": "Vietnamese",
            "th": "Thai",
            "sv": "Swedish",
            "da": "Danish",
            "fi": "Finnish",
            "no": "Norwegian",
            "cs": "Czech",
            "el": "Greek",
            "he": "Hebrew",
            "hu": "Hungarian",
            "id": "Indonesian",
            "ms": "Malay",
            "ro": "Romanian",
            "sk": "Slovak",
            "uk": "Ukrainian",
            "bg": "Bulgarian",
            "hr": "Croatian",
            "lt": "Lithuanian",
            "lv": "Latvian",
            "sl": "Slovenian",
            "et": "Estonian",
            "bn": "Bengali",
            "ta": "Tamil",
            "te": "Telugu",
            "mr": "Marathi",
            "gu": "Gujarati",
            "kn": "Kannada",
            "ml": "Malayalam",
            "pa": "Punjabi",
            "ur": "Urdu",
            "fa": "Persian",
            "af": "Afrikaans",
            "sw": "Swahili",
            "tl": "Tagalog",
            "ca": "Catalan",
            "cy": "Welsh",
            "eu": "Basque",
            "gl": "Galician",
        }
        return language_names.get(lang_code, lang_code.upper())
