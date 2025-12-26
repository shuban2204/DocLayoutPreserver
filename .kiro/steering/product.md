# Product Overview

Document Translator is a layout-preserving PDF translation system. It extracts text from PDFs (both native text and OCR from images), translates content via Gemini API, and reconstructs the PDF while maintaining the original layout and visual appearance.

## Key Capabilities

- Extract native text and images with layout metadata from PDFs
- OCR text extraction from embedded images using PaddleOCR
- Batch translation via Gemini API with retry logic
- Auto-adjust font sizes to fit translated text within original text boxes
- GPU-accelerated processing with CPU fallback
- Multi-document batch processing support

## Target Users

Users who need to translate PDF documents while preserving the original document structure, formatting, and visual layout.
