# Requirements Document

## Introduction

A document translation system that preserves the original layout of PDF documents while translating text content. The system handles both native text and text embedded in images using OCR, translates via Gemini API with batch processing, runs on GPU for performance, and automatically adjusts font sizes to fit translated text within original text boxes.

## Glossary

- **Document_Translator**: The main system responsible for orchestrating the translation pipeline
- **PDF_Parser**: Component that extracts content (text, images, layout metadata) from PDF documents using PyMuPDF
- **OCR_Engine**: Component that extracts text from images using PaddleOCR with GPU acceleration
- **Translation_Service**: Component that translates text using Gemini API with batch calling support
- **Layout_Reconstructor**: Component that rebuilds the PDF with translated content while preserving original layout
- **Font_Adjuster**: Component that calculates and applies appropriate font sizes to fit translated text in original text boxes
- **Text_Block**: A bounded region containing text with position, dimensions, and styling information
- **Image_Region**: An area in the PDF containing an image that may have embedded text
- **Table_Detector**: Component that identifies and extracts table structures from PDF documents
- **Table_Cell**: A single cell within a table with its boundaries, content, and row/column position
- **Table_Structure**: Complete table representation including cells, rows, columns, and borders
- **Language_Detector**: Component that automatically detects the source language of document text

## Requirements

### Requirement 1: PDF Content Extraction

**User Story:** As a user, I want to upload a PDF document and have the system extract all text and images with their layout information, so that the translation can preserve the original document structure.

#### Acceptance Criteria

1. WHEN a valid PDF file is provided, THE PDF_Parser SHALL extract all native text blocks with their bounding box coordinates, font information, and styling
2. WHEN a PDF contains embedded images, THE PDF_Parser SHALL extract each image along with its position and dimensions in the document
3. WHEN extracting text blocks, THE PDF_Parser SHALL preserve the reading order of the content
4. WHEN a PDF has multiple pages, THE PDF_Parser SHALL process each page independently while maintaining page sequence
5. IF an invalid or corrupted PDF is provided, THEN THE PDF_Parser SHALL return a descriptive error message

### Requirement 2: OCR Text Extraction from Images

**User Story:** As a user, I want text within images to be automatically detected and extracted, so that all document content can be translated regardless of whether it's native text or image-embedded text.

#### Acceptance Criteria

1. WHEN an image region is identified, THE OCR_Engine SHALL detect and extract all text within the image using PaddleOCR
2. WHEN extracting text from images, THE OCR_Engine SHALL return bounding box coordinates for each detected text region relative to the image
3. WHEN processing images, THE OCR_Engine SHALL utilize GPU acceleration for improved performance
4. WHEN text is detected in an image, THE OCR_Engine SHALL preserve the detected text's orientation and reading order
5. IF an image contains no detectable text, THEN THE OCR_Engine SHALL return an empty result without error
6. WHEN processing multiple images, THE OCR_Engine SHALL support batch processing for efficiency

### Requirement 3: Text Translation via Gemini API

**User Story:** As a user, I want all extracted text to be translated using Gemini API, so that I get high-quality translations with support for multiple languages.

#### Acceptance Criteria

1. WHEN text content is provided for translation, THE Translation_Service SHALL send requests to Gemini API and return translated text
2. WHEN multiple text blocks require translation, THE Translation_Service SHALL use batch calling to minimize API round trips
3. WHEN translating text, THE Translation_Service SHALL preserve formatting markers and special characters where applicable
4. WHEN a target language is specified, THE Translation_Service SHALL translate all text to that language
5. IF the Gemini API returns an error, THEN THE Translation_Service SHALL retry with exponential backoff up to 3 times
6. IF translation fails after retries, THEN THE Translation_Service SHALL log the error and return the original text with an error flag

### Requirement 4: Layout-Preserving PDF Reconstruction

**User Story:** As a user, I want the translated document to maintain the exact same layout as the original, so that the document structure and visual appearance are preserved.

#### Acceptance Criteria

1. WHEN reconstructing the PDF, THE Layout_Reconstructor SHALL place translated text blocks at the same coordinates as the original text
2. WHEN an image contained text, THE Layout_Reconstructor SHALL overlay translated text on the image at the detected positions
3. WHEN rebuilding the document, THE Layout_Reconstructor SHALL preserve all non-text elements (images, graphics, borders) in their original positions
4. WHEN the translated text is longer than the original, THE Font_Adjuster SHALL reduce font size to fit within the original text box boundaries
5. WHEN the translated text is shorter than the original, THE Font_Adjuster SHALL maintain the original font size
6. WHEN adjusting font size, THE Font_Adjuster SHALL not reduce below a minimum readable size of 6pt
7. WHEN a page is reconstructed, THE Layout_Reconstructor SHALL maintain the original page dimensions and margins

### Requirement 5: GPU Acceleration

**User Story:** As a user, I want the translation pipeline to run on GPU, so that processing is fast even for large documents with many images.

#### Acceptance Criteria

1. WHEN the system initializes, THE Document_Translator SHALL detect available GPU resources and configure components accordingly
2. WHEN GPU is available, THE OCR_Engine SHALL execute PaddleOCR inference on GPU
3. WHEN GPU is not available, THE Document_Translator SHALL fall back to CPU processing with a warning message
4. WHEN processing large documents, THE Document_Translator SHALL manage GPU memory efficiently to prevent out-of-memory errors

### Requirement 6: Batch Processing Support

**User Story:** As a user, I want to translate multiple documents or process large documents efficiently, so that I can handle bulk translation tasks.

#### Acceptance Criteria

1. WHEN multiple PDF files are provided, THE Document_Translator SHALL process them sequentially with progress reporting
2. WHEN translating text, THE Translation_Service SHALL batch multiple text blocks into single API calls where possible
3. WHEN batching API calls, THE Translation_Service SHALL respect Gemini API rate limits and payload size constraints
4. WHEN processing completes, THE Document_Translator SHALL provide a summary of processed documents and any errors encountered

### Requirement 7: Font Size Auto-Adjustment for Text Boxes

**User Story:** As a user, I want translated text to automatically fit within the original text boxes by adjusting font size, so that the document layout is not broken by longer translations.

#### Acceptance Criteria

1. WHEN translated text exceeds the original text box width, THE Font_Adjuster SHALL calculate the maximum font size that fits the text within the box
2. WHEN calculating font size, THE Font_Adjuster SHALL consider both width and height constraints of the text box
3. WHEN multiple lines are required, THE Font_Adjuster SHALL calculate line breaks and adjust font size to fit all lines within the box height
4. WHEN font adjustment is applied, THE Font_Adjuster SHALL attempt to match the original font family or use a similar fallback font
5. WHEN the minimum font size (6pt) cannot fit the text, THE Font_Adjuster SHALL truncate with ellipsis and log a warning

### Requirement 8: Table Detection and Handling

**User Story:** As a user, I want tables in my PDF documents to be properly detected and translated while preserving their structure, so that tabular data remains readable and correctly formatted.

#### Acceptance Criteria

1. WHEN a PDF page contains tables, THE Table_Detector SHALL identify table regions and extract their structure (rows, columns, cells)
2. WHEN extracting table cells, THE Table_Detector SHALL preserve cell boundaries, merged cells, and cell relationships
3. WHEN translating table content, THE Translation_Service SHALL translate each cell independently while maintaining cell context
4. WHEN reconstructing tables, THE Layout_Reconstructor SHALL preserve table borders, cell boundaries, and alignment
5. WHEN translated cell text exceeds cell boundaries, THE Font_Adjuster SHALL reduce font size to fit within the cell without overflowing into adjacent cells
6. WHEN a table spans multiple pages, THE Table_Detector SHALL handle continuation and maintain table integrity
7. IF table detection fails, THEN THE PDF_Parser SHALL fall back to standard text block extraction for that region

### Requirement 9: Automatic Language Detection

**User Story:** As a user, I want the system to automatically detect the source language of my PDF document, so that I don't need to manually specify it and can simply provide the target language.

#### Acceptance Criteria

1. WHEN a PDF is processed, THE Language_Detector SHALL analyze extracted text to determine the source language
2. WHEN detecting language, THE Language_Detector SHALL sample text from multiple pages for accuracy
3. WHEN the source language is detected, THE Translation_Service SHALL use it for translation without user input
4. WHEN multiple languages are detected in a document, THE Language_Detector SHALL identify the primary language and report secondary languages
5. IF language detection confidence is below threshold, THEN THE Language_Detector SHALL log a warning and use the detected language with reduced confidence
6. WHEN the user explicitly provides a source language, THE Document_Translator SHALL use the user-specified language instead of auto-detection
