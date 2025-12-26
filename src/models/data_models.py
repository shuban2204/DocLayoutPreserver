"""Core data models for the Document Translator system."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Any
from enum import Enum


class ContentType(Enum):
    """Type of content in a PDF document."""
    NATIVE_TEXT = "native_text"
    IMAGE_TEXT = "image_text"
    IMAGE = "image"
    GRAPHIC = "graphic"
    TABLE_CELL = "table_cell"


@dataclass
class BoundingBox:
    """Represents a rectangular region with coordinates."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        """Calculate the width of the bounding box."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Calculate the height of the bounding box."""
        return self.y1 - self.y0

    def contains(self, other: 'BoundingBox') -> bool:
        """Check if this bounding box contains another."""
        return (self.x0 <= other.x0 and self.y0 <= other.y0 and
                self.x1 >= other.x1 and self.y1 >= other.y1)

    def to_tuple(self) -> Tuple[float, float, float, float]:
        """Convert to tuple format (x0, y0, x1, y1)."""
        return (self.x0, self.y0, self.x1, self.y1)

    @classmethod
    def from_tuple(cls, t: Tuple[float, float, float, float]) -> 'BoundingBox':
        """Create BoundingBox from tuple."""
        return cls(x0=t[0], y0=t[1], x1=t[2], y1=t[3])


@dataclass
class FontInfo:
    """Font information for text styling."""
    name: str
    size: float
    color: Tuple[int, int, int] = (0, 0, 0)  # RGB, default black
    is_bold: bool = False
    is_italic: bool = False


@dataclass
class TextBlock:
    """A bounded region containing text with position and styling."""
    text: str
    bbox: BoundingBox
    font_name: str
    font_size: float
    page_number: int
    is_from_image: bool = False
    image_index: Optional[int] = None
    font_info: Optional[FontInfo] = None

    @property
    def bbox_tuple(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return self.bbox.to_tuple()


@dataclass
class ImageRegion:
    """An area in the PDF containing an image."""
    image_data: bytes
    bbox: BoundingBox
    page_number: int
    index: int

    @property
    def bbox_tuple(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return self.bbox.to_tuple()


@dataclass
class PageContent:
    """Content extracted from a single PDF page."""
    page_number: int
    width: float
    height: float
    text_blocks: List[TextBlock] = field(default_factory=list)
    image_regions: List[ImageRegion] = field(default_factory=list)
    raw_elements: List[Any] = field(default_factory=list)


@dataclass
class OCRResult:
    """Result from OCR text extraction."""
    text: str
    bbox: BoundingBox
    confidence: float

    @property
    def bbox_tuple(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return self.bbox.to_tuple()


@dataclass
class TranslationUnit:
    """A unit of text to be translated with all metadata."""
    id: str
    original_text: str
    translated_text: Optional[str]
    bbox: BoundingBox
    font_info: FontInfo
    page_number: int
    content_type: ContentType
    parent_image_index: Optional[int] = None
    table_cell_info: Optional[Tuple[int, int, int]] = None  # (table_index, row, col)


@dataclass
class TableCell:
    """A single cell within a table."""
    text: str
    bbox: BoundingBox
    row_index: int
    col_index: int
    row_span: int = 1
    col_span: int = 1
    font_info: Optional[FontInfo] = None

    @property
    def bbox_tuple(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return self.bbox.to_tuple()


@dataclass
class TableStructure:
    """Complete table representation."""
    bbox: BoundingBox
    cells: List[TableCell]
    num_rows: int
    num_cols: int
    page_number: int
    index: int
    has_header: bool = False
    borders: List[Tuple[float, float, float, float]] = field(default_factory=list)

    @property
    def bbox_tuple(self) -> Tuple[float, float, float, float]:
        """Get bounding box as tuple."""
        return self.bbox.to_tuple()


@dataclass
class LanguageDetectionResult:
    """Result of automatic language detection."""
    primary_language: str
    confidence: float
    secondary_languages: List[Tuple[str, float]] = field(default_factory=list)
    sample_size: int = 0
