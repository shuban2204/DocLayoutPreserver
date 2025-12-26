# Tech Stack

## Language
- Python

## Core Libraries
- `pymupdf` (fitz) - PDF parsing and reconstruction
- `paddleocr` - OCR text extraction from images (GPU-accelerated)
- `google-generativeai` - Gemini API for translation
- `hypothesis` - Property-based testing
- `pytest` - Test framework

## Architecture Pattern
Pipeline architecture with distinct processing stages:
1. PDF Parser → extracts text blocks and images
2. OCR Engine → extracts text from images
3. Translation Service → batched Gemini API calls
4. Font Adjuster → calculates text fitting
5. Layout Reconstructor → rebuilds PDF with translations

## Common Commands

```bash
# Install dependencies
pip install pymupdf paddleocr google-generativeai hypothesis pytest

# Run tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_pdf_parser.py

# Run property tests only
pytest -k "property"
```

## Configuration
- GPU detection is automatic; falls back to CPU if unavailable
- Gemini API key required via `TranslationConfig`
- Minimum font size: 6pt (text truncated with ellipsis if cannot fit)
- API retry: 3 attempts with exponential backoff
