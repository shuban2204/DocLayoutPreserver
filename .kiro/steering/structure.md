# Project Structure

```
src/
├── main.py                 # CLI entry point
├── app.py                  # Streamlit web frontend
├── models/
│   ├── data_models.py      # Core dataclasses (BoundingBox, TextBlock, ImageRegion, PageContent, FontInfo, TranslationUnit, TableCell, TableStructure)
│   └── config.py           # TranslationConfig, TranslationSummary
├── services/
│   ├── pdf_parser.py       # PDFParser - extracts content from PDFs
│   ├── table_detector.py   # TableDetector - identifies table structures
│   ├── language_detector.py # LanguageDetector - auto-detects source language
│   ├── ocr_engine.py       # OCREngine - PaddleOCR text extraction
│   ├── translation_service.py  # TranslationService - Gemini API integration
│   ├── font_adjuster.py    # FontAdjuster - text fitting calculations
│   ├── layout_reconstructor.py # LayoutReconstructor - PDF rebuilding
│   └── document_translator.py  # DocumentTranslator - main orchestrator
└── utils/
    └── error_handler.py    # ErrorHandler, ProcessingError

tests/
├── conftest.py             # Pytest fixtures and configuration
└── ...                     # Test files
```

## Key Components

| Component | Responsibility |
|-----------|----------------|
| `PDFParser` | Extract text blocks, images, and layout metadata from PDFs |
| `TableDetector` | Identify table structures and extract cells |
| `LanguageDetector` | Auto-detect source language from text |
| `OCREngine` | Extract text from images with bounding boxes |
| `TranslationService` | Batch translate text via Gemini API with retry logic |
| `FontAdjuster` | Calculate font sizes and line breaks to fit text in boxes |
| `LayoutReconstructor` | Rebuild PDF with translated content preserving layout |
| `DocumentTranslator` | Orchestrate the full translation pipeline |
