"""Table Detector component for identifying and extracting table structures from PDFs."""

import logging
from typing import List, Tuple, Optional, Any
import fitz  # PyMuPDF

from models.data_models import (
    BoundingBox,
    TableCell,
    TableStructure,
    FontInfo,
)


logger = logging.getLogger(__name__)


class TableDetectionError(Exception):
    """Exception raised when table detection fails."""
    pass


class TableDetector:
    """Identifies and extracts table structures from PDF documents."""

    def __init__(self):
        """Initialize the table detector."""
        self._min_table_rows = 2
        self._min_table_cols = 2

    def detect_tables(self, page: fitz.Page, page_num: int) -> List[TableStructure]:
        """
        Detect all tables on a PDF page.
        
        Args:
            page: PyMuPDF page object
            page_num: Page number (0-indexed)
            
        Returns:
            List of TableStructure objects found on the page
        """
        tables: List[TableStructure] = []
        
        try:
            # Use PyMuPDF's built-in table finder
            table_finder = page.find_tables()
            
            for table_idx, table in enumerate(table_finder.tables):
                table_structure = self._process_table(table, page, page_num, table_idx)
                if table_structure:
                    tables.append(table_structure)
                    
        except Exception as e:
            # If table detection fails, return empty list (fallback to text extraction)
            pass
        
        return tables

    def _process_table(
        self, 
        table: Any, 
        page: fitz.Page, 
        page_num: int, 
        table_idx: int
    ) -> Optional[TableStructure]:
        """
        Process a detected table and extract its structure.
        
        Args:
            table: PyMuPDF Table object
            page: PyMuPDF page object
            page_num: Page number
            table_idx: Index of the table on the page
            
        Returns:
            TableStructure object or None if invalid
        """
        try:
            # Get table bounding box
            bbox = BoundingBox(
                x0=table.bbox[0],
                y0=table.bbox[1],
                x1=table.bbox[2],
                y1=table.bbox[3],
            )
            
            # Extract cells
            cells = self.extract_cells(table, page)
            
            if not cells:
                return None
            
            # Calculate dimensions
            num_rows = max(cell.row_index for cell in cells) + 1
            num_cols = max(cell.col_index for cell in cells) + 1
            
            # Skip tables that are too small
            if num_rows < self._min_table_rows or num_cols < self._min_table_cols:
                return None
            
            # Identify merged cells
            cells = self.identify_merged_cells(cells, table)
            
            # Extract borders
            borders = self._extract_borders(table)
            
            # Detect if first row is header
            has_header = self._detect_header(cells)
            
            return TableStructure(
                bbox=bbox,
                cells=cells,
                num_rows=num_rows,
                num_cols=num_cols,
                page_number=page_num,
                index=table_idx,
                has_header=has_header,
                borders=borders,
            )
            
        except Exception:
            return None

    def extract_cells(self, table: Any, page: fitz.Page) -> List[TableCell]:
        """
        Extract cells from a detected table with row/column positions.
        
        Args:
            table: PyMuPDF Table object
            page: PyMuPDF page object
            
        Returns:
            List of TableCell objects
        """
        cells: List[TableCell] = []
        
        try:
            # Get table data as list of rows
            table_data = table.extract()
            
            # Get cell rectangles directly from table
            cell_rects = []
            if hasattr(table, 'cells') and table.cells:
                cell_rects = list(table.cells)
            
            num_rows = len(table_data)
            num_cols = len(table_data[0]) if table_data else 0
            
            for row_idx, row in enumerate(table_data):
                for col_idx, cell_text in enumerate(row):
                    # Calculate cell index
                    cell_idx = row_idx * num_cols + col_idx
                    
                    # Get cell rectangle
                    if cell_idx < len(cell_rects) and cell_rects[cell_idx]:
                        cell_rect = cell_rects[cell_idx]
                        bbox = BoundingBox(
                            x0=cell_rect[0],
                            y0=cell_rect[1],
                            x1=cell_rect[2],
                            y1=cell_rect[3],
                        )
                    else:
                        # Estimate cell position from table bbox
                        bbox = self._estimate_cell_bbox(table, row_idx, col_idx, num_rows, num_cols)
                    
                    # Clean cell text
                    text = str(cell_text) if cell_text else ""
                    text = text.strip()
                    
                    # Extract font info from cell region
                    font_info = self._extract_cell_font_info(page, bbox)
                    
                    cell = TableCell(
                        text=text,
                        bbox=bbox,
                        row_index=row_idx,
                        col_index=col_idx,
                        font_info=font_info,
                    )
                    cells.append(cell)
                    
        except Exception as e:
            logger.debug(f"Error extracting cells: {e}")
        
        return cells

    def _estimate_cell_bbox(
        self, 
        table: Any, 
        row_idx: int, 
        col_idx: int, 
        num_rows: int, 
        num_cols: int
    ) -> BoundingBox:
        """
        Estimate cell bounding box when not directly available.
        
        Args:
            table: PyMuPDF Table object
            row_idx: Row index
            col_idx: Column index
            num_rows: Total number of rows
            num_cols: Total number of columns
            
        Returns:
            Estimated BoundingBox
        """
        table_bbox = table.bbox
        table_width = table_bbox[2] - table_bbox[0]
        table_height = table_bbox[3] - table_bbox[1]
        
        cell_width = table_width / num_cols
        cell_height = table_height / num_rows
        
        x0 = table_bbox[0] + col_idx * cell_width
        y0 = table_bbox[1] + row_idx * cell_height
        x1 = x0 + cell_width
        y1 = y0 + cell_height
        
        return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)

    def _extract_cell_font_info(self, page: fitz.Page, bbox: BoundingBox) -> Optional[FontInfo]:
        """
        Extract font information from text within a cell region.
        
        Args:
            page: PyMuPDF page object
            bbox: Cell bounding box
            
        Returns:
            FontInfo or None if no text found
        """
        try:
            rect = fitz.Rect(bbox.x0, bbox.y0, bbox.x1, bbox.y1)
            text_dict = page.get_text("dict", clip=rect)
            
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_name = span.get("font", "unknown")
                        font_size = span.get("size", 12.0)
                        color_int = span.get("color", 0)
                        flags = span.get("flags", 0)
                        
                        # Parse color
                        r = (color_int >> 16) & 0xFF
                        g = (color_int >> 8) & 0xFF
                        b = color_int & 0xFF
                        
                        return FontInfo(
                            name=font_name,
                            size=font_size,
                            color=(r, g, b),
                            is_bold=bool(flags & 2 ** 4),
                            is_italic=bool(flags & 2 ** 1),
                        )
        except Exception:
            pass
        
        return None

    def identify_merged_cells(self, cells: List[TableCell], table: Any) -> List[TableCell]:
        """
        Identify and mark merged cells (colspan/rowspan).
        
        Args:
            cells: List of TableCell objects
            table: PyMuPDF Table object
            
        Returns:
            Updated list of TableCell objects with span information
        """
        if not cells:
            return cells
        
        try:
            # Build a grid to detect merged cells
            max_row = max(c.row_index for c in cells) + 1
            max_col = max(c.col_index for c in cells) + 1
            
            # Create bbox grid
            bbox_grid = [[None for _ in range(max_col)] for _ in range(max_row)]
            for cell in cells:
                bbox_grid[cell.row_index][cell.col_index] = cell.bbox
            
            # Detect merged cells by comparing bounding boxes
            for cell in cells:
                row_span = 1
                col_span = 1
                
                # Check for column span (same row, adjacent columns with same bbox)
                for next_col in range(cell.col_index + 1, max_col):
                    next_bbox = bbox_grid[cell.row_index][next_col]
                    if next_bbox and self._bboxes_overlap_significantly(cell.bbox, next_bbox):
                        col_span += 1
                    else:
                        break
                
                # Check for row span (same column, adjacent rows with same bbox)
                for next_row in range(cell.row_index + 1, max_row):
                    next_bbox = bbox_grid[next_row][cell.col_index]
                    if next_bbox and self._bboxes_overlap_significantly(cell.bbox, next_bbox):
                        row_span += 1
                    else:
                        break
                
                cell.row_span = row_span
                cell.col_span = col_span
                
        except Exception:
            pass
        
        return cells

    def _bboxes_overlap_significantly(self, bbox1: BoundingBox, bbox2: BoundingBox) -> bool:
        """
        Check if two bounding boxes overlap significantly (indicating merged cells).
        
        Args:
            bbox1: First bounding box
            bbox2: Second bounding box
            
        Returns:
            True if boxes overlap significantly
        """
        tolerance = 2.0  # pixels
        
        # Check if bboxes are essentially the same
        return (
            abs(bbox1.x0 - bbox2.x0) < tolerance and
            abs(bbox1.y0 - bbox2.y0) < tolerance and
            abs(bbox1.x1 - bbox2.x1) < tolerance and
            abs(bbox1.y1 - bbox2.y1) < tolerance
        )

    def _extract_borders(self, table: Any) -> List[Tuple[float, float, float, float]]:
        """
        Extract table border line segments.
        
        Args:
            table: PyMuPDF Table object
            
        Returns:
            List of line segments as (x0, y0, x1, y1) tuples
        """
        borders: List[Tuple[float, float, float, float]] = []
        
        try:
            # Get table bbox for outer border
            bbox = table.bbox
            
            # Add outer border lines
            borders.append((bbox[0], bbox[1], bbox[2], bbox[1]))  # Top
            borders.append((bbox[0], bbox[3], bbox[2], bbox[3]))  # Bottom
            borders.append((bbox[0], bbox[1], bbox[0], bbox[3]))  # Left
            borders.append((bbox[2], bbox[1], bbox[2], bbox[3]))  # Right
            
            # Try to get internal grid lines from cells
            if hasattr(table, 'cells') and table.cells:
                seen_lines = set()
                for cell_rect in table.cells:
                    if cell_rect:
                        x0, y0, x1, y1 = cell_rect
                        # Add cell borders (avoiding duplicates)
                        lines = [
                            (x0, y0, x1, y0),  # Top
                            (x0, y1, x1, y1),  # Bottom
                            (x0, y0, x0, y1),  # Left
                            (x1, y0, x1, y1),  # Right
                        ]
                        for line in lines:
                            rounded = tuple(round(v, 1) for v in line)
                            if rounded not in seen_lines:
                                seen_lines.add(rounded)
                                borders.append(line)
                                
        except Exception:
            pass
        
        return borders

    def _detect_header(self, cells: List[TableCell]) -> bool:
        """
        Detect if the first row is a header row.
        
        Args:
            cells: List of TableCell objects
            
        Returns:
            True if first row appears to be a header
        """
        if not cells:
            return False
        
        # Get first row cells
        first_row_cells = [c for c in cells if c.row_index == 0]
        other_cells = [c for c in cells if c.row_index > 0]
        
        if not first_row_cells or not other_cells:
            return False
        
        # Check if first row has different styling (bold, larger font)
        first_row_bold_count = sum(
            1 for c in first_row_cells 
            if c.font_info and c.font_info.is_bold
        )
        
        # If majority of first row is bold, likely a header
        if first_row_bold_count > len(first_row_cells) / 2:
            return True
        
        # Check if first row has larger font size
        first_row_sizes = [
            c.font_info.size for c in first_row_cells 
            if c.font_info
        ]
        other_sizes = [
            c.font_info.size for c in other_cells 
            if c.font_info
        ]
        
        if first_row_sizes and other_sizes:
            avg_first = sum(first_row_sizes) / len(first_row_sizes)
            avg_other = sum(other_sizes) / len(other_sizes)
            if avg_first > avg_other * 1.1:  # 10% larger
                return True
        
        return False
