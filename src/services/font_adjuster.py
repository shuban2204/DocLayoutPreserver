"""Font Adjuster component for fitting translated text within original text boxes."""

import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

import fitz  # PyMuPDF

from models.data_models import BoundingBox


logger = logging.getLogger(__name__)


@dataclass
class FontAdjustment:
    """Result of font adjustment calculation."""
    original_font_size: float
    adjusted_font_size: float
    font_name: str
    line_breaks: List[int]  # Character positions for line breaks
    is_truncated: bool
    truncated_text: Optional[str] = None  # Text after truncation (if any)


class FontAdjuster:
    """Calculates appropriate font sizes to fit translated text in original boxes."""

    MIN_FONT_SIZE: float = 6.0
    ELLIPSIS: str = "..."
    LINE_SPACING: float = 1.2  # Line height multiplier
    PADDING: float = 2.0  # Padding inside text box

    # Fallback fonts in order of preference
    FALLBACK_FONTS: List[str] = [
        "helv",  # Helvetica
        "tiro",  # Times Roman
        "cour",  # Courier
    ]

    def __init__(self, min_font_size: float = 6.0):
        """
        Initialize the font adjuster.
        
        Args:
            min_font_size: Minimum allowed font size
        """
        self.MIN_FONT_SIZE = min_font_size

    def calculate_fit(
        self,
        text: str,
        bbox: BoundingBox,
        original_font_name: str,
        original_font_size: float
    ) -> FontAdjustment:
        """
        Calculate font size and line breaks to fit text in bbox.
        
        Args:
            text: Text to fit
            bbox: Target bounding box
            original_font_name: Original font name
            original_font_size: Original font size
            
        Returns:
            FontAdjustment with calculated parameters
        """
        if not text or not text.strip():
            return FontAdjustment(
                original_font_size=original_font_size,
                adjusted_font_size=original_font_size,
                font_name=original_font_name,
                line_breaks=[],
                is_truncated=False,
            )
        
        # Get available dimensions (with padding)
        available_width = bbox.width - (2 * self.PADDING)
        available_height = bbox.height - (2 * self.PADDING)
        
        if available_width <= 0 or available_height <= 0:
            return FontAdjustment(
                original_font_size=original_font_size,
                adjusted_font_size=self.MIN_FONT_SIZE,
                font_name=original_font_name,
                line_breaks=[],
                is_truncated=True,
                truncated_text=self.ELLIPSIS,
            )
        
        # Get usable font
        font_name = self._get_usable_font(original_font_name)
        
        # Try original font size first
        font_size = original_font_size
        
        # Binary search for optimal font size
        result = self._find_optimal_fit(
            text, font_name, font_size, available_width, available_height
        )
        
        return result

    def calculate_cell_fit(
        self,
        text: str,
        cell_bbox: BoundingBox,
        original_font_name: str,
        original_font_size: float,
        adjacent_cells: Optional[List[BoundingBox]] = None
    ) -> FontAdjustment:
        """
        Calculate font size for table cell, respecting cell boundaries.
        
        Args:
            text: Text to fit
            cell_bbox: Cell bounding box
            original_font_name: Original font name
            original_font_size: Original font size
            adjacent_cells: Bounding boxes of adjacent cells (to prevent overflow)
            
        Returns:
            FontAdjustment with calculated parameters
        """
        # For table cells, use stricter constraints
        # Reduce available space to ensure no overflow
        cell_padding = self.PADDING * 2  # Extra padding for cells
        
        effective_bbox = BoundingBox(
            x0=cell_bbox.x0 + cell_padding,
            y0=cell_bbox.y0 + cell_padding,
            x1=cell_bbox.x1 - cell_padding,
            y1=cell_bbox.y1 - cell_padding,
        )
        
        return self.calculate_fit(text, effective_bbox, original_font_name, original_font_size)

    def _find_optimal_fit(
        self,
        text: str,
        font_name: str,
        original_font_size: float,
        available_width: float,
        available_height: float
    ) -> FontAdjustment:
        """
        Find optimal font size using binary search.
        
        Args:
            text: Text to fit
            font_name: Font name to use
            original_font_size: Starting font size
            available_width: Available width
            available_height: Available height
            
        Returns:
            FontAdjustment with optimal parameters
        """
        # Try original size first
        line_breaks, fits = self._calculate_line_breaks(
            text, font_name, original_font_size, available_width, available_height
        )
        
        if fits:
            return FontAdjustment(
                original_font_size=original_font_size,
                adjusted_font_size=original_font_size,
                font_name=font_name,
                line_breaks=line_breaks,
                is_truncated=False,
            )
        
        # Binary search for optimal font size
        min_size = self.MIN_FONT_SIZE
        max_size = original_font_size
        best_size = min_size
        best_line_breaks = []
        
        while max_size - min_size > 0.5:
            mid_size = (min_size + max_size) / 2
            line_breaks, fits = self._calculate_line_breaks(
                text, font_name, mid_size, available_width, available_height
            )
            
            if fits:
                best_size = mid_size
                best_line_breaks = line_breaks
                min_size = mid_size
            else:
                max_size = mid_size
        
        # Check if minimum font size works
        if best_size <= self.MIN_FONT_SIZE:
            line_breaks, fits = self._calculate_line_breaks(
                text, font_name, self.MIN_FONT_SIZE, available_width, available_height
            )
            
            if not fits:
                # Need to truncate
                truncated_text = self._truncate_text(
                    text, font_name, self.MIN_FONT_SIZE, available_width, available_height
                )
                truncated_breaks, _ = self._calculate_line_breaks(
                    truncated_text, font_name, self.MIN_FONT_SIZE, available_width, available_height
                )
                
                return FontAdjustment(
                    original_font_size=original_font_size,
                    adjusted_font_size=self.MIN_FONT_SIZE,
                    font_name=font_name,
                    line_breaks=truncated_breaks,
                    is_truncated=True,
                    truncated_text=truncated_text,
                )
            
            best_size = self.MIN_FONT_SIZE
            best_line_breaks = line_breaks
        
        return FontAdjustment(
            original_font_size=original_font_size,
            adjusted_font_size=best_size,
            font_name=font_name,
            line_breaks=best_line_breaks,
            is_truncated=False,
        )

    def measure_text(
        self, 
        text: str, 
        font_name: str, 
        font_size: float
    ) -> Tuple[float, float]:
        """
        Measure text dimensions for given font settings.
        
        Args:
            text: Text to measure
            font_name: Font name
            font_size: Font size
            
        Returns:
            Tuple of (width, height)
        """
        try:
            font = fitz.Font(font_name)
            text_length = font.text_length(text, fontsize=font_size)
            # Approximate height based on font size
            height = font_size * self.LINE_SPACING
            return (text_length, height)
        except Exception:
            # Fallback: estimate based on character count
            avg_char_width = font_size * 0.6
            width = len(text) * avg_char_width
            height = font_size * self.LINE_SPACING
            return (width, height)

    def _calculate_line_breaks(
        self,
        text: str,
        font_name: str,
        font_size: float,
        available_width: float,
        available_height: float
    ) -> Tuple[List[int], bool]:
        """
        Calculate line breaks for text at given font size.
        
        Args:
            text: Text to wrap
            font_name: Font name
            font_size: Font size
            available_width: Available width
            available_height: Available height
            
        Returns:
            Tuple of (line_break_positions, fits_in_box)
        """
        if not text:
            return [], True
        
        line_breaks: List[int] = []
        words = text.split()
        
        if not words:
            return [], True
        
        try:
            font = fitz.Font(font_name)
        except Exception:
            font = fitz.Font("helv")  # Fallback
        
        current_line = ""
        current_pos = 0
        line_count = 0
        line_height = font_size * self.LINE_SPACING
        max_lines = int(available_height / line_height)
        
        if max_lines < 1:
            return [], False
        
        for word in words:
            test_line = f"{current_line} {word}".strip() if current_line else word
            width = font.text_length(test_line, fontsize=font_size)
            
            if width <= available_width:
                current_line = test_line
            else:
                # Need line break
                if current_line:
                    line_count += 1
                    if line_count >= max_lines:
                        return line_breaks, False
                    
                    # Record break position
                    current_pos += len(current_line) + 1
                    line_breaks.append(current_pos - 1)
                
                current_line = word
                
                # Check if single word is too wide
                word_width = font.text_length(word, fontsize=font_size)
                if word_width > available_width:
                    return line_breaks, False
        
        # Check final line
        if current_line:
            line_count += 1
        
        fits = line_count <= max_lines
        return line_breaks, fits

    def _truncate_text(
        self,
        text: str,
        font_name: str,
        font_size: float,
        available_width: float,
        available_height: float
    ) -> str:
        """
        Truncate text with ellipsis to fit in box.
        
        Args:
            text: Text to truncate
            font_name: Font name
            font_size: Font size
            available_width: Available width
            available_height: Available height
            
        Returns:
            Truncated text with ellipsis
        """
        try:
            font = fitz.Font(font_name)
        except Exception:
            font = fitz.Font("helv")
        
        ellipsis_width = font.text_length(self.ELLIPSIS, fontsize=font_size)
        line_height = font_size * self.LINE_SPACING
        max_lines = max(1, int(available_height / line_height))
        
        # Calculate approximate characters that fit
        lines: List[str] = []
        remaining_text = text
        
        for line_num in range(max_lines):
            is_last_line = (line_num == max_lines - 1)
            target_width = available_width - (ellipsis_width if is_last_line else 0)
            
            # Find how much text fits on this line
            line_text = ""
            for char in remaining_text:
                test_text = line_text + char
                if font.text_length(test_text, fontsize=font_size) > target_width:
                    break
                line_text = test_text
            
            if is_last_line and remaining_text[len(line_text):].strip():
                line_text = line_text.rstrip() + self.ELLIPSIS
            
            lines.append(line_text)
            remaining_text = remaining_text[len(line_text.rstrip(self.ELLIPSIS)):]
            
            if not remaining_text.strip():
                break
        
        return "\n".join(lines)

    def _get_usable_font(self, font_name: str) -> str:
        """
        Get a usable font name, falling back if necessary.
        
        Args:
            font_name: Requested font name
            
        Returns:
            Usable font name
        """
        # Try the requested font
        try:
            fitz.Font(font_name)
            return font_name
        except Exception:
            pass
        
        # Try fallback fonts
        for fallback in self.FALLBACK_FONTS:
            try:
                fitz.Font(fallback)
                return fallback
            except Exception:
                continue
        
        # Default to Helvetica
        return "helv"
