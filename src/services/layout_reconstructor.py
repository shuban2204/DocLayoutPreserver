"""Layout Reconstructor component for rebuilding PDFs with translated content."""

import logging
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass

import fitz  # PyMuPDF

from models.data_models import (
    BoundingBox,
    PageContent,
    TextBlock,
    TableStructure,
    TableCell,
)
from services.font_adjuster import FontAdjuster, FontAdjustment


logger = logging.getLogger(__name__)


@dataclass
class ReconstructedBlock:
    """A text block ready for reconstruction."""
    translated_text: str
    bbox: BoundingBox
    font_adjustment: FontAdjustment
    page_number: int
    is_image_overlay: bool = False
    is_table_cell: bool = False
    original_font_color: Tuple[int, int, int] = (0, 0, 0)
    original_font_name: str = "helv"
    original_font_size: float = 12.0


class LayoutReconstructionError(Exception):
    """Exception raised when layout reconstruction fails."""
    pass


class LayoutReconstructor:
    """Rebuilds the PDF with translated content while preserving layout."""

    def __init__(self, original_pdf_path: str, target_language: str = "en"):
        self._original_path = original_pdf_path
        self._target_language = target_language.lower()
        self._doc: Optional[fitz.Document] = None
        self._output_doc: Optional[fitz.Document] = None
        self._font_adjuster = FontAdjuster()
        self._font_cache: Dict[str, fitz.Font] = {}

    def _get_font(self, font_name: str = "helv") -> fitz.Font:
        """Get or create a font object."""
        if font_name not in self._font_cache:
            try:
                self._font_cache[font_name] = fitz.Font(font_name)
            except:
                if "helv" not in self._font_cache:
                    self._font_cache["helv"] = fitz.Font("helv")
                return self._font_cache["helv"]
        return self._font_cache[font_name]

    def _open_documents(self) -> None:
        """Open the original PDF and create output document."""
        if self._doc is None:
            self._doc = fitz.open(self._original_path)
            self._output_doc = fitz.open(self._original_path)

    def _close_documents(self) -> None:
        """Close opened documents."""
        if self._doc:
            self._doc.close()
            self._doc = None
        if self._output_doc:
            self._output_doc.close()
            self._output_doc = None

    def reconstruct(
        self,
        pages: List[PageContent],
        translated_blocks: List[ReconstructedBlock],
        tables: Optional[List[TableStructure]] = None
    ) -> bytes:
        """
        Reconstruct PDF with translated content.
        
        Uses a careful approach:
        1. For each text block, draw white rectangle over original
        2. Insert translated text at exact same position
        3. Preserve all other elements
        """
        self._open_documents()
        
        try:
            # Group blocks by page
            blocks_by_page: Dict[int, List[ReconstructedBlock]] = {}
            for block in translated_blocks:
                if block.page_number not in blocks_by_page:
                    blocks_by_page[block.page_number] = []
                blocks_by_page[block.page_number].append(block)
            
            # Process each page
            for page_num in range(len(self._output_doc)):
                page = self._output_doc[page_num]
                page_blocks = blocks_by_page.get(page_num, [])
                
                if not page_blocks:
                    continue
                
                # Sort blocks by position (top to bottom, left to right)
                page_blocks.sort(key=lambda b: (b.bbox.y0, b.bbox.x0))
                
                # Process each block
                for block in page_blocks:
                    self._replace_text_block(page, block)
            
            return self._output_doc.tobytes()
            
        finally:
            self._close_documents()

    def _replace_text_block(self, page: fitz.Page, block: ReconstructedBlock) -> None:
        """Replace original text with translated text at the same position."""
        if not block.translated_text or not block.translated_text.strip():
            return
        
        # Create rectangle for the text area
        rect = fitz.Rect(block.bbox.x0, block.bbox.y0, block.bbox.x1, block.bbox.y1)
        
        # Step 1: Cover original text with white rectangle
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(color=(1, 1, 1), fill=(1, 1, 1))
        shape.commit()
        
        # Step 2: Insert translated text
        self._insert_fitted_text(page, block)

    def _insert_fitted_text(self, page: fitz.Page, block: ReconstructedBlock) -> None:
        """Insert text that fits within the bounding box."""
        text = block.translated_text.strip()
        if not text:
            return
        
        # Get dimensions
        padding = 1
        x0 = block.bbox.x0 + padding
        y0 = block.bbox.y0 + padding
        x1 = block.bbox.x1 - padding
        y1 = block.bbox.y1 - padding
        
        available_width = x1 - x0
        available_height = y1 - y0
        
        if available_width <= 0 or available_height <= 0:
            return
        
        # Get font and initial size
        font = self._get_font()
        font_size = min(block.original_font_size, block.font_adjustment.adjusted_font_size)
        
        # Convert color
        color = tuple(c / 255.0 for c in block.original_font_color)
        
        # Calculate how many lines we can fit
        line_height = font_size * 1.15
        max_lines = max(1, int(available_height / line_height))
        
        # Wrap text to fit width
        lines = self._wrap_text_smart(text, font, font_size, available_width)
        
        # If too many lines, reduce font size
        while len(lines) > max_lines and font_size > 5:
            font_size -= 0.5
            line_height = font_size * 1.15
            max_lines = max(1, int(available_height / line_height))
            lines = self._wrap_text_smart(text, font, font_size, available_width)
        
        # Truncate if still too many lines
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            if lines and len(lines[-1]) > 3:
                lines[-1] = lines[-1][:-3] + "..."
        
        # Insert text using TextWriter
        try:
            tw = fitz.TextWriter(page.rect)
            y = y0 + font_size  # Start at baseline
            
            for line in lines:
                if y > y1:
                    break
                try:
                    tw.append((x0, y), line, font=font, fontsize=font_size)
                except:
                    pass
                y += line_height
            
            tw.write_text(page, color=color)
        except Exception as e:
            # Fallback: use insert_textbox
            try:
                rect = fitz.Rect(x0, y0, x1, y1)
                page.insert_textbox(
                    rect,
                    text,
                    fontsize=font_size,
                    color=color,
                    align=fitz.TEXT_ALIGN_LEFT,
                )
            except:
                logger.debug(f"Text insertion failed: {e}")

    def _wrap_text_smart(
        self, 
        text: str, 
        font: fitz.Font, 
        font_size: float, 
        max_width: float
    ) -> List[str]:
        """Wrap text intelligently to fit within max_width."""
        if not text:
            return []
        
        # Handle newlines in original text
        paragraphs = text.split('\n')
        all_lines = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            words = para.split()
            if not words:
                continue
            
            current_line = ""
            
            for word in words:
                test_line = f"{current_line} {word}".strip() if current_line else word
                
                try:
                    width = font.text_length(test_line, fontsize=font_size)
                except:
                    width = len(test_line) * font_size * 0.5
                
                if width <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        all_lines.append(current_line)
                    
                    # Check if word itself is too long
                    try:
                        word_width = font.text_length(word, fontsize=font_size)
                    except:
                        word_width = len(word) * font_size * 0.5
                    
                    if word_width > max_width:
                        # Break the word
                        broken = self._break_word(word, font, font_size, max_width)
                        if broken:
                            all_lines.extend(broken[:-1])
                            current_line = broken[-1] if broken else ""
                        else:
                            current_line = word[:1]
                    else:
                        current_line = word
            
            if current_line:
                all_lines.append(current_line)
        
        return all_lines if all_lines else [text[:20] + "..." if len(text) > 20 else text]

    def _break_word(
        self, 
        word: str, 
        font: fitz.Font, 
        font_size: float, 
        max_width: float
    ) -> List[str]:
        """Break a long word into multiple lines."""
        parts = []
        current = ""
        
        for char in word:
            test = current + char
            try:
                width = font.text_length(test, fontsize=font_size)
            except:
                width = len(test) * font_size * 0.5
            
            if width <= max_width:
                current = test
            else:
                if current:
                    parts.append(current)
                current = char
        
        if current:
            parts.append(current)
        
        return parts

    def save(self, output_path: str, pdf_bytes: Optional[bytes] = None) -> None:
        """Save reconstructed PDF to file."""
        if pdf_bytes:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
        elif self._output_doc:
            self._output_doc.save(output_path)
        else:
            raise LayoutReconstructionError("No PDF content to save")

    def get_page_dimensions(self, page_num: int) -> Tuple[float, float]:
        """Get dimensions of a specific page."""
        self._open_documents()
        if page_num >= len(self._doc):
            raise LayoutReconstructionError(f"Page {page_num} does not exist")
        page = self._doc[page_num]
        return (page.rect.width, page.rect.height)

    def prepare_block(
        self,
        translated_text: str,
        original_block: TextBlock,
        font_adjustment: Optional[FontAdjustment] = None
    ) -> ReconstructedBlock:
        """Prepare a text block for reconstruction."""
        if font_adjustment is None:
            font_adjustment = self._font_adjuster.calculate_fit(
                translated_text,
                original_block.bbox,
                original_block.font_name,
                original_block.font_size,
            )
        
        color = (0, 0, 0)
        if original_block.font_info:
            color = original_block.font_info.color
        
        return ReconstructedBlock(
            translated_text=translated_text,
            bbox=original_block.bbox,
            font_adjustment=font_adjustment,
            page_number=original_block.page_number,
            is_image_overlay=original_block.is_from_image,
            original_font_color=color,
            original_font_name=original_block.font_name,
            original_font_size=original_block.font_size,
        )

    def prepare_table_cell_block(
        self,
        translated_text: str,
        cell: TableCell,
        page_number: int
    ) -> ReconstructedBlock:
        """Prepare a table cell for reconstruction."""
        original_font_size = cell.font_info.size if cell.font_info else 10.0
        original_font_name = cell.font_info.name if cell.font_info else "helv"
        
        font_adjustment = self._font_adjuster.calculate_cell_fit(
            translated_text,
            cell.bbox,
            original_font_name,
            original_font_size,
        )
        
        color = (0, 0, 0)
        if cell.font_info:
            color = cell.font_info.color
        
        return ReconstructedBlock(
            translated_text=translated_text,
            bbox=cell.bbox,
            font_adjustment=font_adjustment,
            page_number=page_number,
            is_table_cell=True,
            original_font_color=color,
            original_font_name=original_font_name,
            original_font_size=original_font_size,
        )
