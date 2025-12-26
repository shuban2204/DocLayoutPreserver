# Project Structure

```
src/
├── main.py                 # CLI entry point
├── models/
│   ├── data_models.py      # Core dataclasses (BoundingBox, TextBlock, ImageRegion, PageContent, FontInfo, TranslationUnit)
│   └── config.py           # TranslationConfig, TranslationSummary
├── services/
│   ├── pdf_parser.py       # PDFParser - extracts content from PDFs
│   ├── ocr_engine.py       # OCREngine - PaddleOCR text extraction
│   ├── translation_service.py  # TranslationService - Gemini API integration
│   ├── font_adjuster.py    # FontAdjuster - text fitting calculations
│   ├── layout_reconstructor.py # LayoutReconstructor - PDF rebuilding
│   └── document_translator.py  # DocumentTranslator - main orchestrator
└── utils/
    └── error_handler.py    # ErrorHandler, ProcessingError

tests/
├── conftest.py             # Pytest fixtures and configuration
├── test_pdf_parser.py      # PDF extraction tests
├── test_ocr_engine.py      # OCR tests
├── test_translation_service.py # Translation tests
├── test_font_adjuster.py   # Font fitting tests
├── test_layout_reconstructor.py # Layout tests
└── test_integration.py     # End-to-end tests
```

## Key Components

| Component | Responsibility |
|-----------|----------------|
| `PDFParser` | Extract text blocks, images, and layout metadata from PDFs |
| `OCREngine` | Extract text from images with bounding boxes |
| `TranslationService` | Batch translate text via Gemini API with retry logic |
| `FontAdjuster` | Calculate font sizes and line breaks to fit text in boxes |
| `LayoutReconstructor` | Rebuild PDF with translated content preserving layout |
| `DocumentTranslator` | Orchestrate the full translation pipeline |
