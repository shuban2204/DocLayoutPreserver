#!/usr/bin/env python3
"""CLI interface for the Document Translator."""

import argparse
import sys
import os
import logging
from pathlib import Path
from typing import List, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from models.config import TranslationConfig
from services.document_translator import DocumentTranslator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Translate PDF documents while preserving layout.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Translate a single PDF to Spanish
  python main.py input.pdf output.pdf --target es --api-key YOUR_API_KEY

  # Translate with explicit source language
  python main.py input.pdf output.pdf --target fr --source en --api-key YOUR_API_KEY

  # Batch translate multiple PDFs
  python main.py --batch input1.pdf:output1.pdf input2.pdf:output2.pdf --target de --api-key YOUR_API_KEY

  # Use GPU acceleration
  python main.py input.pdf output.pdf --target ja --api-key YOUR_API_KEY --gpu
        """,
    )
    
    # Input/output arguments
    parser.add_argument(
        "input",
        nargs="?",
        help="Input PDF file path",
    )
    parser.add_argument(
        "output",
        nargs="?",
        help="Output PDF file path",
    )
    
    # Batch mode
    parser.add_argument(
        "--batch",
        nargs="+",
        metavar="INPUT:OUTPUT",
        help="Batch mode: specify input:output pairs",
    )
    
    # Language options
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target language code (e.g., es, fr, de, ja, zh)",
    )
    parser.add_argument(
        "--source", "-s",
        default=None,
        help="Source language code (auto-detected if not specified)",
    )
    
    # API configuration
    parser.add_argument(
        "--api-key", "-k",
        default=os.environ.get("GEMINI_API_KEY"),
        help="Gemini API key (or set GEMINI_API_KEY env var)",
    )
    
    # Processing options
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Enable GPU acceleration for OCR",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for translation API calls (default: 10)",
    )
    parser.add_argument(
        "--min-font-size",
        type=float,
        default=6.0,
        help="Minimum font size in points (default: 6.0)",
    )
    
    # Output options
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output",
    )
    
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> bool:
    """Validate command-line arguments."""
    # Check API key
    if not args.api_key:
        print("Error: Gemini API key is required. Use --api-key or set GEMINI_API_KEY env var.")
        return False
    
    # Check input/output for single file mode
    if not args.batch:
        if not args.input or not args.output:
            print("Error: Input and output paths are required (or use --batch for batch mode).")
            return False
        
        if not os.path.exists(args.input):
            print(f"Error: Input file not found: {args.input}")
            return False
        
        if not args.input.lower().endswith(".pdf"):
            print(f"Error: Input file must be a PDF: {args.input}")
            return False
    
    # Validate batch mode
    if args.batch:
        for pair in args.batch:
            if ":" not in pair:
                print(f"Error: Invalid batch format '{pair}'. Use INPUT:OUTPUT format.")
                return False
            
            input_path, output_path = pair.split(":", 1)
            if not os.path.exists(input_path):
                print(f"Error: Input file not found: {input_path}")
                return False
    
    return True


def get_input_output_pairs(args: argparse.Namespace) -> List[Tuple[str, str]]:
    """Get list of input/output file pairs."""
    if args.batch:
        pairs = []
        for pair in args.batch:
            input_path, output_path = pair.split(":", 1)
            pairs.append((input_path, output_path))
        return pairs
    else:
        return [(args.input, args.output)]


def print_summary(summaries: list, quiet: bool = False) -> None:
    """Print translation summary."""
    if quiet:
        return
    
    print("\n" + "=" * 60)
    print("TRANSLATION SUMMARY")
    print("=" * 60)
    
    total_pages = 0
    total_blocks = 0
    total_images = 0
    total_time = 0.0
    failed = 0
    
    for summary in summaries:
        status = "✓" if summary.success else "✗"
        print(f"\n{status} {summary.input_file} -> {summary.output_file}")
        print(f"  Pages: {summary.pages_processed}")
        print(f"  Text blocks: {summary.text_blocks_translated}")
        print(f"  Images processed: {summary.images_processed}")
        print(f"  Time: {summary.processing_time_seconds:.2f}s")
        
        if summary.errors:
            print(f"  Errors: {len(summary.errors)}")
            for error in summary.errors[:3]:  # Show first 3 errors
                print(f"    - {error}")
            if len(summary.errors) > 3:
                print(f"    ... and {len(summary.errors) - 3} more")
        
        total_pages += summary.pages_processed
        total_blocks += summary.text_blocks_translated
        total_images += summary.images_processed
        total_time += summary.processing_time_seconds
        if not summary.success:
            failed += 1
    
    print("\n" + "-" * 60)
    print(f"Total: {len(summaries)} documents, {total_pages} pages, "
          f"{total_blocks} text blocks, {total_images} images")
    print(f"Time: {total_time:.2f}s")
    if failed > 0:
        print(f"Failed: {failed} documents")
    print("=" * 60)


def main() -> int:
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    else:
        setup_logging(args.verbose)
    
    # Validate arguments
    if not validate_args(args):
        return 1
    
    # Create configuration
    config = TranslationConfig(
        target_language=args.target,
        gemini_api_key=args.api_key,
        source_language=args.source,
        use_gpu=args.gpu,
        batch_size=args.batch_size,
        min_font_size=args.min_font_size,
    )
    
    # Get input/output pairs
    pairs = get_input_output_pairs(args)
    
    if not args.quiet:
        print(f"Document Translator")
        print(f"Target language: {args.target}")
        if args.source:
            print(f"Source language: {args.source}")
        else:
            print("Source language: auto-detect")
        print(f"GPU: {'enabled' if args.gpu else 'disabled'}")
        print(f"Documents to process: {len(pairs)}")
        print()
    
    # Create translator and process
    translator = DocumentTranslator(config)
    
    if len(pairs) == 1:
        input_path, output_path = pairs[0]
        if not args.quiet:
            print(f"Translating: {input_path}")
        summary = translator.translate_document(input_path, output_path)
        summaries = [summary]
    else:
        summaries = translator.translate_batch(pairs)
    
    # Print summary
    print_summary(summaries, args.quiet)
    
    # Return exit code
    if all(s.success for s in summaries):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
