"""OCR Engine component for extracting text from images using PaddleOCR."""

import io
import logging
from typing import List, Optional

from PIL import Image
import numpy as np

from models.data_models import BoundingBox, OCRResult


logger = logging.getLogger(__name__)


class OCRError(Exception):
    """Exception raised when OCR processing fails."""
    pass


class OCREngine:
    """Handles text extraction from images using PaddleOCR with GPU support."""

    def __init__(self, use_gpu: bool = True, lang: str = "en"):
        """
        Initialize PaddleOCR with GPU configuration.
        
        Args:
            use_gpu: Whether to use GPU acceleration
            lang: Language for OCR (default: "en")
        """
        self._use_gpu = use_gpu and self.is_gpu_available()
        self._lang = lang
        self._ocr = None
        self._initialized = False

    def _initialize_ocr(self) -> None:
        """Lazy initialization of PaddleOCR."""
        if self._initialized:
            return
        
        try:
            from paddleocr import PaddleOCR
            
            self._ocr = PaddleOCR(
                use_angle_cls=True,  # Detect text orientation
                lang=self._lang,
                use_gpu=self._use_gpu,
                show_log=False,
            )
            self._initialized = True
            
        except ImportError:
            raise OCRError("PaddleOCR is not installed. Install with: pip install paddleocr")
        except Exception as e:
            raise OCRError(f"Failed to initialize PaddleOCR: {str(e)}")

    def is_gpu_available(self) -> bool:
        """
        Check if GPU is available for processing.
        
        Returns:
            True if GPU is available
        """
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0
        except ImportError:
            return False
        except Exception:
            return False

    def extract_text(self, image_data: bytes) -> List[OCRResult]:
        """
        Extract text from a single image.
        
        Args:
            image_data: Image data as bytes
            
        Returns:
            List of OCRResult objects with text and bounding boxes
        """
        self._initialize_ocr()
        
        if not image_data:
            return []
        
        try:
            # Convert bytes to numpy array
            image = self._bytes_to_image(image_data)
            if image is None:
                return []
            
            # Run OCR
            result = self._ocr.ocr(image, cls=True)
            
            # Parse results
            return self._parse_ocr_result(result)
            
        except Exception as e:
            logger.warning(f"OCR extraction failed: {str(e)}")
            return []

    def extract_text_batch(self, images: List[bytes]) -> List[List[OCRResult]]:
        """
        Extract text from multiple images in batch.
        
        Args:
            images: List of image data as bytes
            
        Returns:
            List of OCRResult lists, one per image
        """
        self._initialize_ocr()
        
        if not images:
            return []
        
        results: List[List[OCRResult]] = []
        
        # Process images in batch
        # Note: PaddleOCR processes one image at a time internally,
        # but we can still benefit from GPU memory management
        for image_data in images:
            try:
                ocr_results = self.extract_text(image_data)
                results.append(ocr_results)
            except Exception as e:
                logger.warning(f"Batch OCR failed for image: {str(e)}")
                results.append([])
        
        return results

    def _bytes_to_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """
        Convert image bytes to numpy array.
        
        Args:
            image_data: Image data as bytes
            
        Returns:
            Numpy array or None if conversion fails
        """
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            return np.array(image)
            
        except Exception as e:
            logger.warning(f"Failed to convert image: {str(e)}")
            return None

    def _parse_ocr_result(self, result: List) -> List[OCRResult]:
        """
        Parse PaddleOCR result into OCRResult objects.
        
        Args:
            result: Raw PaddleOCR result
            
        Returns:
            List of OCRResult objects
        """
        ocr_results: List[OCRResult] = []
        
        if not result or not result[0]:
            return ocr_results
        
        for line in result[0]:
            try:
                # line format: [[[x1,y1], [x2,y2], [x3,y3], [x4,y4]], (text, confidence)]
                if len(line) < 2:
                    continue
                
                bbox_points = line[0]
                text_info = line[1]
                
                if not bbox_points or not text_info:
                    continue
                
                # Extract text and confidence
                text = text_info[0] if isinstance(text_info, (list, tuple)) else str(text_info)
                confidence = float(text_info[1]) if isinstance(text_info, (list, tuple)) and len(text_info) > 1 else 0.0
                
                # Convert polygon to bounding box
                bbox = self._polygon_to_bbox(bbox_points)
                
                if text.strip():
                    ocr_results.append(OCRResult(
                        text=text.strip(),
                        bbox=bbox,
                        confidence=confidence,
                    ))
                    
            except Exception as e:
                logger.debug(f"Failed to parse OCR line: {str(e)}")
                continue
        
        # Sort by reading order (top to bottom, left to right)
        ocr_results = self._sort_by_reading_order(ocr_results)
        
        return ocr_results

    def _polygon_to_bbox(self, points: List[List[float]]) -> BoundingBox:
        """
        Convert polygon points to bounding box.
        
        Args:
            points: List of [x, y] points
            
        Returns:
            BoundingBox object
        """
        if not points or len(points) < 4:
            return BoundingBox(x0=0, y0=0, x1=0, y1=0)
        
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        
        return BoundingBox(
            x0=min(x_coords),
            y0=min(y_coords),
            x1=max(x_coords),
            y1=max(y_coords),
        )

    def _sort_by_reading_order(self, results: List[OCRResult]) -> List[OCRResult]:
        """
        Sort OCR results by reading order.
        
        Args:
            results: List of OCRResult objects
            
        Returns:
            Sorted list
        """
        if not results:
            return results
        
        tolerance = 10.0  # pixels
        
        def get_sort_key(result: OCRResult):
            y_rounded = round(result.bbox.y0 / tolerance) * tolerance
            return (y_rounded, result.bbox.x0)
        
        return sorted(results, key=get_sort_key)

    def set_language(self, lang: str) -> None:
        """
        Set OCR language and reinitialize.
        
        Args:
            lang: Language code (e.g., "en", "ch", "fr")
        """
        if lang != self._lang:
            self._lang = lang
            self._initialized = False
            self._ocr = None
