# Tech Stack

## Language
- Python

## Core Libraries
- `pymupdf` (fitz) - PDF parsing and reconstruction
- `paddleocr` - OCR text extraction from images (GPU-accelerated)
- `google-generativeai` - Gemini API for translation
- `hypothesis` - Property-based testing
- `pytest` - Test framework
- `langdetect` - Automatic language detection
- `streamlit` - Web frontend

## Architecture Pattern
Pipeline architecture with distinct processing stages:
1. PDF Parser → extracts text blocks and images
2. Table Detector → identifies table structures
3. Language Detector → auto-detects source language
4. OCR Engine → extracts text from images
5. Translation Service → batched Gemini API calls
6. Font Adjuster → calculates text fitting
7. Layout Reconstructor → rebuilds PDF with translations

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI
python src/main.py input.pdf output.pdf --target es --api-key YOUR_KEY

# Run web frontend
streamlit run src/app.py

# Run tests
pytest

# Run with verbose output
pytest -v
```

## Configuration
- GPU detection is automatic; falls back to CPU if unavailable
- Gemini API key required via `TranslationConfig` or `GEMINI_API_KEY` env var
- Minimum font size: 6pt (text truncated with ellipsis if cannot fit)
- API retry: 3 attempts with exponential backoff
