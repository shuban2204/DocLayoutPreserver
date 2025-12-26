"""Document Translator orchestrator - main entry point for the translation pipeline."""

import time
import logging
from typing import List, Tuple, Optional
import uuid

from models.data_models import (
    TextBlock,
    PageContent,
    TableStructure,
    ContentType,
)
from models.config import TranslationConfig, TranslationSummary
from services.pdf_parser import PDFParser, PDFParseError
from services.table_detector import TableDetector
from services.language_detector import LanguageDetector, LanguageDetectionError
from services.ocr_engine import OCREngine, OCRError
from services.translation_service import TranslationService, TranslationRequest, TranslationError
from services.font_adjuster import FontAdjuster
from services.layout_reconstructor import LayoutReconstructor, ReconstructedBlock


logger = logging.getLogger(__name__)


class DocumentTranslationError(Exception):
    """Exception raised when document translation fails."""
    pass


class DocumentTranslator:
    """Main orchestrator that coordinates the entire translation pipeline."""

    def __init__(self, config: TranslationConfig):
        """
        Initialize translator with configuration.
        
        Args:
            config: TranslationConfig with API key, languages, etc.
        """
        self._config = config
        self._pdf_parser = PDFParser()
        self._table_detector = TableDetector()
        self._language_detector = LanguageDetector()
        self._ocr_engine: Optional[OCREngine] = None
        self._translation_service: Optional[TranslationService] = None
        self._font_adjuster = FontAdjuster(min_font_size=config.min_font_size)
        
        # Initialize GPU-dependent components lazily
        self._gpu_available: Optional[bool] = None

    def _initialize_components(self) -> None:
        """Initialize GPU-dependent components."""
        if self._ocr_engine is None:
            use_gpu = self._config.use_gpu and self._is_gpu_available()
            self._ocr_engine = OCREngine(use_gpu=use_gpu)
            
            if self._config.use_gpu and not use_gpu:
                logger.warning("GPU requested but not available, falling back to CPU")
        
        if self._translation_service is None:
            self._translation_service = TranslationService(
                api_key=self._config.gemini_api_key,
                target_lang=self._config.target_language,
                source_lang=self._config.source_language,
            )

    def _is_gpu_available(self) -> bool:
        """Check if GPU is available."""
        if self._gpu_available is None:
            try:
                import paddle
                self._gpu_available = (
                    paddle.device.is_compiled_with_cuda() and 
                    paddle.device.cuda.device_count() > 0
                )
            except ImportError:
                self._gpu_available = False
            except Exception:
                self._gpu_available = False
        return self._gpu_available

    def translate_document(self, input_path: str, output_path: str) -> TranslationSummary:
        """
        Translate a single PDF document.
        
        Args:
            input_path: Path to input PDF
            output_path: Path for output PDF
            
        Returns:
            TranslationSummary with statistics
        """
        start_time = time.time()
        summary = TranslationSummary(
            input_file=input_path,
            output_file=output_path,
        )
        
        try:
            self._initialize_components()
            
            # Step 1: Parse PDF
            logger.info(f"Parsing PDF: {input_path}")
            pages = self._pdf_parser.parse(input_path)
            summary.pages_processed = len(pages)
            
            # Step 2: Detect tables
            logger.info("Detecting tables...")
            all_tables: List[TableStructure] = []
            import fitz
            doc = fitz.open(input_path)
            for page_num, page_content in enumerate(pages):
                page = doc[page_num]
                tables = self._table_detector.detect_tables(page, page_num)
                all_tables.extend(tables)
            doc.close()
            
            # Step 3: Collect all text blocks (excluding those inside tables)
            logger.info("Collecting text blocks...")
            all_text_blocks: List[TextBlock] = []
            for page in pages:
                for block in page.text_blocks:
                    # Check if block is inside a table
                    is_in_table = self._is_block_in_table(block, all_tables)
                    if not is_in_table:
                        all_text_blocks.append(block)
            
            # Step 4: Extract text from images (OCR)
            logger.info("Processing images with OCR...")
            ocr_blocks = self._process_images(pages)
            all_text_blocks.extend(ocr_blocks)
            summary.images_processed = sum(len(p.image_regions) for p in pages)
            
            # Step 5: Collect table cell text
            table_cell_blocks = self._collect_table_cells(all_tables)
            
            # Step 6: Detect source language (if not specified)
            source_lang = self._config.source_language
            if not source_lang:
                logger.info("Detecting source language...")
                detection_result = self._language_detector.detect_language(all_text_blocks)
                source_lang = detection_result.primary_language
                logger.info(f"Detected language: {source_lang} (confidence: {detection_result.confidence:.2f})")
                
                if detection_result.secondary_languages:
                    logger.info(f"Secondary languages: {detection_result.secondary_languages}")
                
                self._translation_service.set_source_language(source_lang)
            
            # Step 7: Translate all text
            logger.info("Translating text...")
            translated_blocks = self._translate_blocks(all_text_blocks)
            translated_table_cells = self._translate_table_cells(table_cell_blocks, all_tables)
            summary.text_blocks_translated = len(translated_blocks) + len(translated_table_cells)
            
            # Step 8: Reconstruct PDF
            logger.info("Reconstructing PDF...")
            reconstructor = LayoutReconstructor(input_path, self._config.target_language)
            
            # Prepare blocks for reconstruction
            reconstructed_blocks = self._prepare_reconstructed_blocks(
                all_text_blocks, translated_blocks, pages
            )
            reconstructed_blocks.extend(translated_table_cells)
            
            # Reconstruct and save
            pdf_bytes = reconstructor.reconstruct(pages, reconstructed_blocks, all_tables)
            reconstructor.save(output_path, pdf_bytes)
            
            logger.info(f"Translation complete: {output_path}")
            
        except PDFParseError as e:
            summary.add_error(f"PDF parsing error: {str(e)}")
            logger.error(f"PDF parsing failed: {str(e)}")
        except TranslationError as e:
            summary.add_error(f"Translation error: {str(e)}")
            logger.error(f"Translation failed: {str(e)}")
        except Exception as e:
            summary.add_error(f"Unexpected error: {str(e)}")
            logger.error(f"Translation failed: {str(e)}")
        
        summary.processing_time_seconds = time.time() - start_time
        return summary

    def translate_batch(
        self, 
        input_output_pairs: List[Tuple[str, str]]
    ) -> List[TranslationSummary]:
        """
        Translate multiple PDF documents.
        
        Args:
            input_output_pairs: List of (input_path, output_path) tuples
            
        Returns:
            List of TranslationSummary objects
        """
        summaries: List[TranslationSummary] = []
        total = len(input_output_pairs)
        
        for i, (input_path, output_path) in enumerate(input_output_pairs):
            logger.info(f"Processing document {i + 1}/{total}: {input_path}")
            summary = self.translate_document(input_path, output_path)
            summaries.append(summary)
            
            if summary.success:
                logger.info(f"Completed: {input_path} -> {output_path}")
            else:
                logger.warning(f"Failed: {input_path}, errors: {summary.errors}")
        
        return summaries

    def _process_images(self, pages: List[PageContent]) -> List[TextBlock]:
        """
        Process images with OCR to extract text.
        
        Args:
            pages: List of PageContent with images
            
        Returns:
            List of TextBlock objects from OCR
        """
        ocr_blocks: List[TextBlock] = []
        
        for page in pages:
            for image_region in page.image_regions:
                try:
                    ocr_results = self._ocr_engine.extract_text(image_region.image_data)
                    
                    for ocr_result in ocr_results:
                        # Convert OCR bbox (relative to image) to page coordinates
                        page_bbox = self._convert_ocr_bbox_to_page(
                            ocr_result.bbox,
                            image_region.bbox,
                        )
                        
                        block = TextBlock(
                            text=ocr_result.text,
                            bbox=page_bbox,
                            font_name="helv",  # Default for OCR text
                            font_size=12.0,
                            page_number=page.page_number,
                            is_from_image=True,
                            image_index=image_region.index,
                        )
                        ocr_blocks.append(block)
                        
                except OCRError as e:
                    logger.warning(f"OCR failed for image {image_region.index}: {str(e)}")
                except Exception as e:
                    logger.warning(f"Error processing image: {str(e)}")
        
        return ocr_blocks

    def _convert_ocr_bbox_to_page(
        self,
        ocr_bbox,
        image_bbox
    ):
        """
        Convert OCR bounding box (relative to image) to page coordinates.
        
        Args:
            ocr_bbox: BoundingBox relative to image
            image_bbox: BoundingBox of image on page
            
        Returns:
            BoundingBox in page coordinates
        """
        from models.data_models import BoundingBox
        
        # OCR bbox is relative to image, need to scale and offset
        image_width = image_bbox.width
        image_height = image_bbox.height
        
        # Assuming OCR bbox is in pixel coordinates of the image
        # Scale to page coordinates
        scale_x = image_width / max(ocr_bbox.x1, 1)
        scale_y = image_height / max(ocr_bbox.y1, 1)
        
        return BoundingBox(
            x0=image_bbox.x0 + ocr_bbox.x0 * scale_x,
            y0=image_bbox.y0 + ocr_bbox.y0 * scale_y,
            x1=image_bbox.x0 + ocr_bbox.x1 * scale_x,
            y1=image_bbox.y0 + ocr_bbox.y1 * scale_y,
        )

    def _collect_table_cells(
        self, 
        tables: List[TableStructure]
    ) -> List[Tuple[str, TableStructure, int, int]]:
        """
        Collect text from table cells for translation.
        
        Args:
            tables: List of TableStructure objects
            
        Returns:
            List of (text, table, row, col) tuples
        """
        cell_texts: List[Tuple[str, TableStructure, int, int]] = []
        
        for table in tables:
            for cell in table.cells:
                if cell.text.strip():
                    cell_texts.append((cell.text, table, cell.row_index, cell.col_index))
        
        return cell_texts

    def _translate_blocks(
        self, 
        text_blocks: List[TextBlock]
    ) -> dict:
        """
        Translate text blocks.
        
        Args:
            text_blocks: List of TextBlock objects
            
        Returns:
            Dict mapping block index to translated text
        """
        if not text_blocks:
            return {}
        
        # Create translation requests for non-empty blocks
        requests: List[TranslationRequest] = []
        block_indices: List[int] = []  # Track which blocks have requests
        
        for i, block in enumerate(text_blocks):
            if block.text.strip():
                requests.append(TranslationRequest(
                    text=block.text,
                    source_lang=self._config.source_language,
                    target_lang=self._config.target_language,
                    block_id=str(i),
                ))
                block_indices.append(i)
        
        if not requests:
            return {}
        
        # Translate in batches
        results = self._translation_service.translate_batch(requests)
        
        # Map results back to blocks
        translations = {}
        for j, result in enumerate(results):
            if j < len(block_indices):
                idx = block_indices[j]
                # Use translated text if available, otherwise keep original
                translated = result.translated_text.strip() if result.translated_text else ""
                if translated:
                    translations[idx] = translated
                else:
                    # Fallback to original text
                    translations[idx] = text_blocks[idx].text
        
        return translations

    def _translate_table_cells(
        self,
        cell_texts: List[Tuple[str, TableStructure, int, int]],
        tables: List[TableStructure]
    ) -> List[ReconstructedBlock]:
        """
        Translate table cells and prepare for reconstruction.
        
        Args:
            cell_texts: List of (text, table, row, col) tuples
            tables: List of TableStructure objects
            
        Returns:
            List of ReconstructedBlock for table cells
        """
        if not cell_texts:
            return []
        
        # Create translation requests
        requests: List[TranslationRequest] = []
        for i, (text, table, row, col) in enumerate(cell_texts):
            requests.append(TranslationRequest(
                text=text,
                source_lang=self._config.source_language,
                target_lang=self._config.target_language,
                block_id=f"cell_{i}",
            ))
        
        # Translate
        results = self._translation_service.translate_batch(requests)
        
        # Prepare reconstructed blocks
        reconstructed: List[ReconstructedBlock] = []
        reconstructor = LayoutReconstructor.__new__(LayoutReconstructor)
        reconstructor._font_adjuster = self._font_adjuster
        reconstructor._target_language = self._config.target_language
        reconstructor._selected_font = None
        reconstructor._font_cache = {}
        
        for i, result in enumerate(results):
            if i < len(cell_texts):
                original_text, table, row, col = cell_texts[i]
                # Find the cell
                cell = None
                for c in table.cells:
                    if c.row_index == row and c.col_index == col:
                        cell = c
                        break
                
                if cell:
                    # Use translated text if available, otherwise keep original
                    translated = result.translated_text.strip() if result.translated_text else ""
                    if not translated:
                        translated = original_text
                    
                    block = reconstructor.prepare_table_cell_block(
                        translated,
                        cell,
                        table.page_number,
                    )
                    reconstructed.append(block)
        
        return reconstructed

    def _prepare_reconstructed_blocks(
        self,
        text_blocks: List[TextBlock],
        translations: dict,
        pages: List[PageContent]
    ) -> List[ReconstructedBlock]:
        """
        Prepare text blocks for reconstruction.
        
        Args:
            text_blocks: Original text blocks
            translations: Dict mapping block index to translated text
            pages: Original page content
            
        Returns:
            List of ReconstructedBlock objects
        """
        reconstructed: List[ReconstructedBlock] = []
        
        for i, block in enumerate(text_blocks):
            translated_text = translations.get(i, block.text)
            
            # Calculate font adjustment
            font_adjustment = self._font_adjuster.calculate_fit(
                translated_text,
                block.bbox,
                block.font_name,
                block.font_size,
            )
            
            # Get original color
            color = (0, 0, 0)
            if block.font_info:
                color = block.font_info.color
            
            reconstructed.append(ReconstructedBlock(
                translated_text=translated_text,
                bbox=block.bbox,
                font_adjustment=font_adjustment,
                page_number=block.page_number,
                is_image_overlay=block.is_from_image,
                original_font_color=color,
            ))
        
        return reconstructed

    def _is_block_in_table(self, block: TextBlock, tables: List[TableStructure]) -> bool:
        """
        Check if a text block is significantly inside any table region.
        
        Args:
            block: TextBlock to check
            tables: List of detected tables
            
        Returns:
            True if block is mostly inside a table
        """
        for table in tables:
            if table.page_number != block.page_number:
                continue
            
            # Calculate overlap between block and table
            overlap_x0 = max(block.bbox.x0, table.bbox.x0)
            overlap_y0 = max(block.bbox.y0, table.bbox.y0)
            overlap_x1 = min(block.bbox.x1, table.bbox.x1)
            overlap_y1 = min(block.bbox.y1, table.bbox.y1)
            
            if overlap_x1 > overlap_x0 and overlap_y1 > overlap_y0:
                overlap_area = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
                block_area = block.bbox.width * block.bbox.height
                
                # Only consider it "in table" if >80% of block is inside table
                if block_area > 0 and overlap_area / block_area > 0.8:
                    return True
        
        return False

    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported target languages.
        
        Returns:
            List of language codes
        """
        return [
            "en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko",
            "ar", "hi", "nl", "pl", "tr", "vi", "th", "sv", "da", "fi",
            "no", "cs", "el", "he", "hu", "id", "ms", "ro", "sk", "uk",
        ]
