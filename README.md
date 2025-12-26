# Document Translator

A layout-preserving PDF translation system that extracts text from PDFs (both native text and OCR from images), translates content via Google Gemini API, and reconstructs the PDF while maintaining the original layout and visual appearance.

## Features

- **Layout Preservation**: Maintains original document structure, formatting, and visual layout
- **Table Support**: Detects and translates table content while preserving cell boundaries
- **OCR Integration**: Extracts text from embedded images using PaddleOCR
- **Auto Language Detection**: Automatically detects source language if not specified
- **Batch Translation**: Efficient batched API calls with retry logic
- **GPU Acceleration**: Automatic GPU detection with CPU fallback
- **Web Interface**: User-friendly Streamlit frontend
- **CLI Support**: Command-line interface for automation

## Tech Stack

- **Python 3.10+**
- **PyMuPDF (fitz)** - PDF parsing and reconstruction
- **PaddleOCR** - OCR text extraction from images
- **Google Generative AI** - Gemini API for translation
- **Streamlit** - Web frontend
- **langdetect** - Automatic language detection

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/document-translator.git
cd document-translator
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your Gemini API key:
```bash
# Create a .env file
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

## Usage

### Web Interface (Recommended)

```bash
streamlit run src/app.py
```

Then open http://localhost:8501 in your browser.

### Command Line

```bash
python src/main.py input.pdf output.pdf --target hi --api-key YOUR_API_KEY
```

Options:
- `--target`: Target language code (default: hi for Hindi)
- `--source`: Source language code (auto-detected if not specified)
- `--api-key`: Gemini API key (or set GEMINI_API_KEY env var)
- `--no-gpu`: Disable GPU acceleration

## Supported Languages

English, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Korean, Arabic, Hindi, Dutch, Polish, Turkish, Vietnamese, Thai, Swedish, Danish, Finnish, Norwegian, Czech, Greek, Hebrew, Hungarian, Indonesian, Malay, Romanian, Slovak, Ukrainian, and more.

## Project Structure

```
src/
├── main.py                 # CLI entry point
├── app.py                  # Streamlit web frontend
├── models/
│   ├── data_models.py      # Core dataclasses
│   └── config.py           # Configuration classes
├── services/
│   ├── pdf_parser.py       # PDF content extraction
│   ├── table_detector.py   # Table structure detection
│   ├── language_detector.py # Language auto-detection
│   ├── ocr_engine.py       # PaddleOCR integration
│   ├── translation_service.py  # Gemini API integration
│   ├── font_adjuster.py    # Text fitting calculations
│   ├── layout_reconstructor.py # PDF rebuilding
│   └── document_translator.py  # Main orchestrator
└── utils/
    └── error_handler.py    # Error handling utilities
```

## Configuration

- **GPU**: Automatically detected; falls back to CPU if unavailable
- **API Retry**: 3 attempts with exponential backoff
- **Minimum Font Size**: 5pt (text truncated with ellipsis if cannot fit)
- **Batch Size**: 50 text blocks per API call

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
