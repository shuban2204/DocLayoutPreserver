# Implementation Plan: Document Translator

## Overview

This implementation plan breaks down the document translator into incremental coding tasks. Each task builds on previous work, with property tests placed close to implementation to catch errors early. The system uses Python with PyMuPDF, PaddleOCR, and Gemini API.

## Tasks

- [ ] 1. Set up project structure and core data models
  - Create directory structure: `src/`, `tests/`, `src/models/`, `src/services/`
  - Install dependencies: `pymupdf`, `paddleocr`, `google-generativeai`, `hypothesis`, `pytest`
  - Create `src/models/data_models.py` with `BoundingBox`, `TextBlock`, `ImageRegion`, `PageContent`, `FontInfo`, `TranslationUnit` dataclasses
  - Create `src/models/config.py` with `TranslationConfig` and `TranslationSummary`
  - Set up `pytest.ini` and `conftest.py` for testing
  - _Requirements: 1.1, 2.1, 4.1_

- [ ] 2. Implement PDF Parser component
  - [ ] 2.1 Create `src/services/pdf_parser.py` with `PDFParser` class
    - Implement `validate_pdf()` method to check PDF validity
    - Implement `parse()` method to extract text blocks with bounding boxes, fonts, and styling using PyMuPDF
    - Implement image extraction with position metadata
    - Implement reading order preservation logic
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test for PDF extraction completeness
    - **Property 1: PDF Extraction Completeness**
    - **Validates: Requirements 1.1, 1.2**

  - [ ]* 2.3 Write property test for extraction order preservation
    - **Property 2: Extraction Order Preservation**
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 2.4 Write property test for invalid PDF handling
    - **Property 3: Invalid PDF Error Handling**
    - **Validates: Requirements 1.5**

- [ ] 3. Implement OCR Engine component
  - [ ] 3.1 Create `src/services/ocr_engine.py` with `OCREngine` class
    - Initialize PaddleOCR with GPU configuration
    - Implement `is_gpu_available()` method
    - Implement `extract_text()` for single image processing
    - Implement `extract_text_batch()` for batch processing
    - Return `OCRResult` objects with text and bounding boxes
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 3.2 Write property test for OCR text extraction with positioning
    - **Property 4: OCR Text Extraction with Positioning**
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 3.3 Write property test for OCR batch equivalence
    - **Property 6: OCR Batch Processing Equivalence**
    - **Validates: Requirements 2.6**

- [ ] 4. Checkpoint - Ensure extraction components work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Translation Service component
  - [ ] 5.1 Create `src/services/translation_service.py` with `TranslationService` class
    - Initialize with Gemini API key and target language
    - Implement `_call_gemini_api()` with retry logic and exponential backoff
    - Implement `translate_batch()` for batched translation requests
    - Handle API errors and return original text on failure
    - Preserve formatting markers in translations
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [ ]* 5.2 Write property test for translation batch equivalence
    - **Property 7: Translation Batch Equivalence**
    - **Validates: Requirements 3.2, 6.2**

  - [ ]* 5.3 Write property test for translation retry and fallback
    - **Property 9: Translation Retry and Fallback**
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 5.4 Write property test for formatting preservation
    - **Property 8: Translation Formatting Preservation**
    - **Validates: Requirements 3.3**

- [ ] 6. Implement Font Adjuster component
  - [ ] 6.1 Create `src/services/font_adjuster.py` with `FontAdjuster` class
    - Define `MIN_FONT_SIZE = 6.0` constant
    - Implement `measure_text()` to calculate text dimensions for given font
    - Implement `calculate_fit()` to determine optimal font size and line breaks
    - Handle truncation with ellipsis when text cannot fit at minimum size
    - _Requirements: 4.4, 4.5, 4.6, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 6.2 Write property test for font adjustment text fitting
    - **Property 12: Font Adjustment Text Fitting**
    - **Validates: Requirements 4.4, 4.5, 7.1, 7.2, 7.3**

  - [ ]* 6.3 Write property test for minimum font size invariant
    - **Property 13: Minimum Font Size Invariant**
    - **Validates: Requirements 4.6, 7.5**

- [ ] 7. Checkpoint - Ensure core services work
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Layout Reconstructor component
  - [ ] 8.1 Create `src/services/layout_reconstructor.py` with `LayoutReconstructor` class
    - Initialize with original PDF for structure reference
    - Implement text block placement at original coordinates
    - Implement image text overlay functionality
    - Preserve non-text elements (images, graphics, borders)
    - Maintain page dimensions and margins
    - Implement `reconstruct()` and `save()` methods
    - _Requirements: 4.1, 4.2, 4.3, 4.7_

  - [ ]* 8.2 Write property test for layout coordinate preservation
    - **Property 10: Layout Coordinate Preservation**
    - **Validates: Requirements 4.1, 4.2**

  - [ ]* 8.3 Write property test for non-text element preservation
    - **Property 11: Non-Text Element Preservation**
    - **Validates: Requirements 4.3**

  - [ ]* 8.4 Write property test for page dimension preservation
    - **Property 14: Page Dimension Preservation**
    - **Validates: Requirements 4.7**

- [ ] 9. Implement Document Translator orchestrator
  - [ ] 9.1 Create `src/services/document_translator.py` with `DocumentTranslator` class
    - Initialize with `TranslationConfig`
    - Implement GPU detection and component configuration
    - Implement `translate_document()` for single PDF translation
    - Implement `translate_batch()` for multiple PDF processing
    - Generate accurate `TranslationSummary` with statistics
    - Handle CPU fallback when GPU unavailable
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 6.1, 6.4_

  - [ ]* 9.2 Write property test for processing summary accuracy
    - **Property 15: Processing Summary Accuracy**
    - **Validates: Requirements 6.4**

- [ ] 10. Implement error handling utilities
  - [ ] 10.1 Create `src/utils/error_handler.py` with `ErrorHandler` class
    - Define `ProcessingError` dataclass
    - Implement handlers for PDF, OCR, and translation errors
    - Configure retry settings with exponential backoff
    - _Requirements: 1.5, 3.5, 3.6_

- [ ] 11. Checkpoint - Ensure all components integrate
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. Create CLI interface and main entry point
  - [ ] 12.1 Create `src/main.py` with CLI interface
    - Parse command-line arguments (input PDF, output path, target language, API key)
    - Support single file and batch processing modes
    - Display progress and summary information
    - _Requirements: 6.1, 6.4_

- [ ] 13. Integration testing
  - [ ]* 13.1 Write integration tests for end-to-end translation
    - Test simple PDF translation
    - Test PDF with images containing text
    - Test batch processing of multiple PDFs
    - _Requirements: All_

- [ ] 14. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis
- Unit tests validate specific examples and edge cases
- GPU acceleration is used for PaddleOCR; system falls back to CPU if unavailable
