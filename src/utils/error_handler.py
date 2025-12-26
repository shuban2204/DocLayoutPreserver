"""Error handling utilities for the Document Translator system."""

import logging
import time
from typing import Optional, Callable, Any, List, Type
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps


logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Types of errors in the translation pipeline."""
    PDF_PARSE = "pdf_parse"
    OCR = "ocr"
    TRANSLATION = "translation"
    TABLE_DETECTION = "table_detection"
    LANGUAGE_DETECTION = "language_detection"
    FONT_ADJUSTMENT = "font_adjustment"
    LAYOUT_RECONSTRUCTION = "layout_reconstruction"
    FILE_IO = "file_io"
    API = "api"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


@dataclass
class ProcessingError:
    """Represents an error that occurred during processing."""
    error_type: ErrorType
    message: str
    page_number: Optional[int] = None
    block_id: Optional[str] = None
    recoverable: bool = True
    original_exception: Optional[Exception] = None
    timestamp: float = field(default_factory=time.time)

    def __str__(self) -> str:
        location = ""
        if self.page_number is not None:
            location += f" (page {self.page_number})"
        if self.block_id:
            location += f" (block {self.block_id})"
        return f"[{self.error_type.value}]{location}: {self.message}"


# Retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "initial_delay_seconds": 1.0,
    "exponential_base": 2.0,
    "max_delay_seconds": 30.0,
    "retryable_errors": [
        "RateLimitError",
        "TimeoutError",
        "ConnectionError",
        "ServiceUnavailable",
        "ResourceExhausted",
    ]
}


class ErrorHandler:
    """Handles errors across the translation pipeline."""

    def __init__(self):
        """Initialize the error handler."""
        self._errors: List[ProcessingError] = []
        self._retry_config = RETRY_CONFIG.copy()

    def handle_pdf_error(
        self, 
        error: Exception, 
        path: str,
        page_number: Optional[int] = None
    ) -> ProcessingError:
        """
        Handle PDF parsing errors.
        
        Args:
            error: The exception that occurred
            path: Path to the PDF file
            page_number: Optional page number where error occurred
            
        Returns:
            ProcessingError object
        """
        error_msg = f"PDF error for '{path}': {str(error)}"
        
        processing_error = ProcessingError(
            error_type=ErrorType.PDF_PARSE,
            message=error_msg,
            page_number=page_number,
            recoverable=False,
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        logger.error(str(processing_error))
        
        return processing_error

    def handle_ocr_error(
        self, 
        error: Exception, 
        image_index: int,
        page_number: Optional[int] = None
    ) -> ProcessingError:
        """
        Handle OCR processing errors.
        
        Args:
            error: The exception that occurred
            image_index: Index of the image that failed
            page_number: Optional page number
            
        Returns:
            ProcessingError object
        """
        error_msg = f"OCR error for image {image_index}: {str(error)}"
        
        processing_error = ProcessingError(
            error_type=ErrorType.OCR,
            message=error_msg,
            page_number=page_number,
            block_id=f"image_{image_index}",
            recoverable=True,  # Can skip image and continue
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        logger.warning(str(processing_error))
        
        return processing_error

    def handle_translation_error(
        self, 
        error: Exception, 
        block_id: str,
        page_number: Optional[int] = None
    ) -> ProcessingError:
        """
        Handle translation API errors.
        
        Args:
            error: The exception that occurred
            block_id: ID of the text block that failed
            page_number: Optional page number
            
        Returns:
            ProcessingError object
        """
        error_msg = f"Translation error for block {block_id}: {str(error)}"
        
        # Check if error is retryable
        is_retryable = any(
            err_type in type(error).__name__ 
            for err_type in self._retry_config["retryable_errors"]
        )
        
        processing_error = ProcessingError(
            error_type=ErrorType.TRANSLATION,
            message=error_msg,
            page_number=page_number,
            block_id=block_id,
            recoverable=True,  # Return original text on failure
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        logger.warning(str(processing_error))
        
        return processing_error

    def handle_table_detection_error(
        self,
        error: Exception,
        page_number: int
    ) -> ProcessingError:
        """
        Handle table detection errors.
        
        Args:
            error: The exception that occurred
            page_number: Page number where error occurred
            
        Returns:
            ProcessingError object
        """
        error_msg = f"Table detection error on page {page_number}: {str(error)}"
        
        processing_error = ProcessingError(
            error_type=ErrorType.TABLE_DETECTION,
            message=error_msg,
            page_number=page_number,
            recoverable=True,  # Fall back to text block extraction
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        logger.warning(str(processing_error))
        
        return processing_error

    def handle_language_detection_error(
        self,
        error: Exception
    ) -> ProcessingError:
        """
        Handle language detection errors.
        
        Args:
            error: The exception that occurred
            
        Returns:
            ProcessingError object
        """
        error_msg = f"Language detection error: {str(error)}"
        
        processing_error = ProcessingError(
            error_type=ErrorType.LANGUAGE_DETECTION,
            message=error_msg,
            recoverable=True,  # Can use default or user-specified language
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        logger.warning(str(processing_error))
        
        return processing_error

    def handle_resource_error(
        self,
        error: Exception,
        resource_type: str
    ) -> ProcessingError:
        """
        Handle resource errors (GPU OOM, disk full, etc.).
        
        Args:
            error: The exception that occurred
            resource_type: Type of resource (gpu, disk, memory)
            
        Returns:
            ProcessingError object
        """
        error_msg = f"Resource error ({resource_type}): {str(error)}"
        
        # GPU errors are recoverable (fallback to CPU)
        recoverable = resource_type.lower() == "gpu"
        
        processing_error = ProcessingError(
            error_type=ErrorType.RESOURCE,
            message=error_msg,
            recoverable=recoverable,
            original_exception=error,
        )
        
        self._errors.append(processing_error)
        
        if recoverable:
            logger.warning(str(processing_error))
        else:
            logger.error(str(processing_error))
        
        return processing_error

    def get_errors(self) -> List[ProcessingError]:
        """Get all recorded errors."""
        return self._errors.copy()

    def get_error_summary(self) -> dict:
        """
        Get summary of errors by type.
        
        Returns:
            Dict with error counts by type
        """
        summary = {}
        for error in self._errors:
            error_type = error.error_type.value
            if error_type not in summary:
                summary[error_type] = {"count": 0, "recoverable": 0, "fatal": 0}
            summary[error_type]["count"] += 1
            if error.recoverable:
                summary[error_type]["recoverable"] += 1
            else:
                summary[error_type]["fatal"] += 1
        return summary

    def clear_errors(self) -> None:
        """Clear all recorded errors."""
        self._errors.clear()

    def has_fatal_errors(self) -> bool:
        """Check if any non-recoverable errors occurred."""
        return any(not e.recoverable for e in self._errors)


def retry_with_backoff(
    max_retries: int = RETRY_CONFIG["max_retries"],
    initial_delay: float = RETRY_CONFIG["initial_delay_seconds"],
    exponential_base: float = RETRY_CONFIG["exponential_base"],
    max_delay: float = RETRY_CONFIG["max_delay_seconds"],
    retryable_exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        exponential_base: Base for exponential backoff
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exception types to retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}"
                        )
            
            raise last_exception
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    error_handler: ErrorHandler,
    error_type: ErrorType,
    default_value: Any = None,
    **error_context
) -> Any:
    """
    Safely execute a function and handle errors.
    
    Args:
        func: Function to execute
        error_handler: ErrorHandler instance
        error_type: Type of error to record
        default_value: Value to return on error
        **error_context: Additional context for error (page_number, block_id, etc.)
        
    Returns:
        Function result or default_value on error
    """
    try:
        return func()
    except Exception as e:
        processing_error = ProcessingError(
            error_type=error_type,
            message=str(e),
            page_number=error_context.get("page_number"),
            block_id=error_context.get("block_id"),
            recoverable=True,
            original_exception=e,
        )
        error_handler._errors.append(processing_error)
        logger.warning(str(processing_error))
        return default_value
