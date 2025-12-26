"""PDF Parser component for extracting content from PDF documents."""

import os
from typing import List, Tuple, Optional, Any
import fitz  # PyMuPDF

from models.data_models import (
    BoundingBox,
    TextBlock,
    ImageRegion,
    PageContent,
    FontInfo,
)


class PDFParseError(Exception):
    """Exception raised when PDF parsing fails."""
    pass


class PDFParser:
    """Extracts content from PDF documents using PyMuPDF."""

    def validate_pdf(self, pdf_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate PDF file and return (is_valid, error_message).
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        if not pdf_path:
            return False, "PDF path is empty"
        
        if not os.path.exists(pdf_path):
            return False, f"File not found: {pdf_path}"
        
        if not pdf_path.lower().endswith('.pdf'):
            return False, f"File is not a PDF: {pdf_path}"
        
        try:
            doc = fitz.open(pdf_path)
            if doc.page_count == 0:
                doc.close()
                return False, "PDF has no pages"
            doc.close()
            return True, None
        except fitz.FileDataError as e:
            return False, f"Corrupted or invalid PDF: {str(e)}"
        except fitz.FileNotFoundError:
            return False, f"File not found: {pdf_path}"
        except Exception as e:
            return False, f"Error opening PDF: {str(e)}"

    def parse(self, pdf_path: str) -> List[PageContent]:
        """
        Extract all content from PDF with layout information.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of PageContent objects, one per page
            
        Raises:
            PDFParseError: If the PDF cannot be parsed
        """
        is_valid, error_msg = self.validate_pdf(pdf_path)
        if not is_valid:
            raise PDFParseError(error_msg)
        
        pages: List[PageContent] = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_content = self._extract_page_content(page, page_num)
                pages.append(page_content)
            
            doc.close()
            return pages
            
        except PDFParseError:
            raise
        except Exception as e:
            raise PDFParseError(f"Error parsing PDF: {str(e)}")

    def _extract_page_content(self, page: fitz.Page, page_num: int) -> PageContent:
        """
        Extract content from a single PDF page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)
            
        Returns:
            PageContent object with extracted text blocks and images
        """
        rect = page.rect
        
        # Extract text blocks
        text_blocks = self._extract_text_blocks(page, page_num)
        
        # Extract images
        image_regions = self._extract_images(page, page_num)
        
        # Extract raw elements for preservation
        raw_elements = self._extract_raw_elements(page)
        
        return PageContent(
            page_number=page_num,
            width=rect.width,
            height=rect.height,
            text_blocks=text_blocks,
            image_regions=image_regions,
            raw_elements=raw_elements,
        )

    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> List[TextBlock]:
        """
        Extract text blocks with bounding boxes, fonts, and styling.
        Uses span-level extraction for more accurate positioning.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number
            
        Returns:
            List of TextBlock objects in reading order
        """
        text_blocks: List[TextBlock] = []
        
        # Get text with detailed information using "dict" extraction
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        for block in text_dict.get("blocks", []):
            if block.get("type") != 0:  # 0 = text block
                continue
            
            # Process each line separately for better positioning
            for line in block.get("lines", []):
                line_bbox = line.get("bbox", (0, 0, 0, 0))
                line_text_parts = []
                line_font_name = "unknown"
                line_font_size = 12.0
                line_color = (0, 0, 0)
                line_is_bold = False
                line_is_italic = False
                
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if text:
                        line_text_parts.append(text)
                        # Use first span's font info
                        if line_font_name == "unknown":
                            line_font_name = span.get("font", "unknown")
                            line_font_size = span.get("size", 12.0)
                            color_int = span.get("color", 0)
                            line_color = self._int_to_rgb(color_int)
                            flags = span.get("flags", 0)
                            line_is_bold = bool(flags & 2 ** 4)
                            line_is_italic = bool(flags & 2 ** 1)
                
                full_text = "".join(line_text_parts).strip()
                
                if not full_text:
                    continue
                
                font_info = FontInfo(
                    name=line_font_name,
                    size=line_font_size,
                    color=line_color,
                    is_bold=line_is_bold,
                    is_italic=line_is_italic,
                )
                
                bbox = BoundingBox.from_tuple(line_bbox)
                
                text_block = TextBlock(
                    text=full_text,
                    bbox=bbox,
                    font_name=line_font_name,
                    font_size=line_font_size,
                    page_number=page_num,
                    font_info=font_info,
                )
                text_blocks.append(text_block)
        
        # Merge adjacent blocks that are on the same line
        text_blocks = self._merge_adjacent_blocks(text_blocks)
        
        # Sort by reading order
        text_blocks = self._sort_by_reading_order(text_blocks)
        
        return text_blocks

    def _merge_adjacent_blocks(self, blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Merge text blocks that are on the same line and close together.
        
        Args:
            blocks: List of text blocks
            
        Returns:
            Merged list of text blocks
        """
        if not blocks:
            return blocks
        
        # Sort by y position then x position
        sorted_blocks = sorted(blocks, key=lambda b: (round(b.bbox.y0 / 5) * 5, b.bbox.x0))
        
        merged = []
        current = None
        
        for block in sorted_blocks:
            if current is None:
                current = block
                continue
            
            # Check if blocks are on same line (similar y position)
            same_line = abs(current.bbox.y0 - block.bbox.y0) < 5
            # Check if blocks are close horizontally
            close = block.bbox.x0 - current.bbox.x1 < 20
            # Check if same font
            same_font = (current.font_name == block.font_name and 
                        abs(current.font_size - block.font_size) < 1)
            
            if same_line and close and same_font:
                # Merge blocks
                merged_bbox = BoundingBox(
                    x0=min(current.bbox.x0, block.bbox.x0),
                    y0=min(current.bbox.y0, block.bbox.y0),
                    x1=max(current.bbox.x1, block.bbox.x1),
                    y1=max(current.bbox.y1, block.bbox.y1),
                )
                current = TextBlock(
                    text=current.text + " " + block.text,
                    bbox=merged_bbox,
                    font_name=current.font_name,
                    font_size=current.font_size,
                    page_number=current.page_number,
                    font_info=current.font_info,
                )
            else:
                merged.append(current)
                current = block
        
        if current:
            merged.append(current)
        
        return merged

    def _extract_images(self, page: fitz.Page, page_num: int) -> List[ImageRegion]:
        """
        Extract images with position metadata.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number
            
        Returns:
            List of ImageRegion objects
        """
        image_regions: List[ImageRegion] = []
        
        image_list = page.get_images(full=True)
        
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            
            try:
                # Get image bounding box
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue
                
                img_rect = img_rects[0]  # Use first occurrence
                
                # Extract image data
                base_image = page.parent.extract_image(xref)
                if not base_image:
                    continue
                
                image_data = base_image.get("image", b"")
                if not image_data:
                    continue
                
                bbox = BoundingBox(
                    x0=img_rect.x0,
                    y0=img_rect.y0,
                    x1=img_rect.x1,
                    y1=img_rect.y1,
                )
                
                image_region = ImageRegion(
                    image_data=image_data,
                    bbox=bbox,
                    page_number=page_num,
                    index=img_index,
                )
                image_regions.append(image_region)
                
            except Exception:
                # Skip problematic images
                continue
        
        return image_regions

    def _extract_raw_elements(self, page: fitz.Page) -> List[Any]:
        """
        Extract raw elements for preservation (drawings, graphics, etc.).
        
        Args:
            page: PyMuPDF page object
            
        Returns:
            List of raw drawing elements
        """
        raw_elements: List[Any] = []
        
        try:
            # Get drawings (lines, rectangles, curves, etc.)
            drawings = page.get_drawings()
            for drawing in drawings:
                raw_elements.append({
                    "type": "drawing",
                    "data": drawing,
                })
        except Exception:
            pass
        
        return raw_elements

    def _sort_by_reading_order(self, text_blocks: List[TextBlock]) -> List[TextBlock]:
        """
        Sort text blocks by reading order (top to bottom, left to right).
        
        Args:
            text_blocks: List of text blocks to sort
            
        Returns:
            Sorted list of text blocks
        """
        if not text_blocks:
            return text_blocks
        
        # Group blocks by approximate vertical position (within tolerance)
        tolerance = 5.0  # pixels
        
        def get_sort_key(block: TextBlock) -> Tuple[float, float]:
            # Round y to group blocks on same line
            y_rounded = round(block.bbox.y0 / tolerance) * tolerance
            return (y_rounded, block.bbox.x0)
        
        return sorted(text_blocks, key=get_sort_key)

    def _int_to_rgb(self, color_int: int) -> Tuple[int, int, int]:
        """
        Convert integer color to RGB tuple.
        
        Args:
            color_int: Color as integer
            
        Returns:
            RGB tuple (r, g, b)
        """
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b)
