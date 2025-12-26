"""Configuration and summary models for the Document Translator."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class TranslationConfig:
    """Configuration for the translation pipeline."""
    target_language: str
    gemini_api_key: str
    source_language: Optional[str] = None
    use_gpu: bool = True
    batch_size: int = 10
    min_font_size: float = 6.0
    max_retries: int = 3
    initial_retry_delay: float = 1.0


@dataclass
class TranslationSummary:
    """Summary of a document translation operation."""
    input_file: str
    output_file: str
    pages_processed: int = 0
    text_blocks_translated: int = 0
    images_processed: int = 0
    errors: List[str] = field(default_factory=list)
    processing_time_seconds: float = 0.0
    success: bool = True

    def add_error(self, error: str) -> None:
        """Add an error message to the summary."""
        self.errors.append(error)
        self.success = False
