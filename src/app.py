"""Streamlit web frontend for Document Translator."""

import streamlit as st
import tempfile
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from models.config import TranslationConfig
from services.document_translator import DocumentTranslator

# Language options
LANGUAGES = {
    "Auto-detect": None,
    "English": "en",
    "Spanish": "es",
    "French": "fr",
    "German": "de",
    "Italian": "it",
    "Portuguese": "pt",
    "Russian": "ru",
    "Chinese (Simplified)": "zh-cn",
    "Chinese (Traditional)": "zh-tw",
    "Japanese": "ja",
    "Korean": "ko",
    "Arabic": "ar",
    "Hindi": "hi",
    "Dutch": "nl",
    "Polish": "pl",
    "Turkish": "tr",
    "Vietnamese": "vi",
    "Thai": "th",
    "Swedish": "sv",
    "Danish": "da",
    "Finnish": "fi",
    "Norwegian": "no",
    "Czech": "cs",
    "Greek": "el",
    "Hebrew": "he",
    "Hungarian": "hu",
    "Indonesian": "id",
    "Malay": "ms",
    "Romanian": "ro",
    "Slovak": "sk",
    "Ukrainian": "uk",
    "Bengali": "bn",
    "Tamil": "ta",
    "Telugu": "te",
}

# Target languages (without auto-detect)
TARGET_LANGUAGES = {k: v for k, v in LANGUAGES.items() if v is not None}


def init_session_state():
    """Initialize session state variables."""
    if "translated_pdf" not in st.session_state:
        st.session_state.translated_pdf = None
    if "translation_complete" not in st.session_state:
        st.session_state.translation_complete = False
    if "summary" not in st.session_state:
        st.session_state.summary = None


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Document Translator",
        page_icon="📄",
        layout="centered",
    )
    
    init_session_state()
    
    # Header
    st.title("📄 Document Translator")
    st.markdown("Translate PDF documents while preserving layout")
    st.divider()
    
    # Get API key from environment (hidden from user)
    api_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY not found in environment. Please set it in your .env file.")
        st.stop()
    
    # File upload
    uploaded_file = st.file_uploader(
        "Upload PDF Document",
        type=["pdf"],
        help="Upload the PDF document you want to translate",
    )
    
    if uploaded_file is None:
        st.info("Please upload a PDF document to translate.")
        return
    
    # Show file info
    st.success(f"Uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
    
    st.divider()
    
    # Language selection
    col1, col2 = st.columns(2)
    
    with col1:
        source_lang_name = st.selectbox(
            "Source Language",
            options=list(LANGUAGES.keys()),
            index=0,  # Default to Auto-detect
            help="Select the language of the input document, or choose Auto-detect",
        )
        source_lang = LANGUAGES[source_lang_name]
    
    with col2:
        target_lang_name = st.selectbox(
            "Target Language",
            options=list(TARGET_LANGUAGES.keys()),
            index=1,  # Default to Spanish
            help="Select the language to translate to",
        )
        target_lang = TARGET_LANGUAGES[target_lang_name]
    
    # Show selected options
    if source_lang:
        st.caption(f"Translating from **{source_lang_name}** to **{target_lang_name}**")
    else:
        st.caption(f"Auto-detecting source language, translating to **{target_lang_name}**")
    
    st.divider()

    # Advanced options
    with st.expander("Advanced Options"):
        use_gpu = st.checkbox(
            "Use GPU Acceleration",
            value=False,
            help="Enable GPU for faster OCR processing (requires CUDA)",
        )
        
        min_font_size = st.slider(
            "Minimum Font Size (pt)",
            min_value=4.0,
            max_value=12.0,
            value=6.0,
            step=0.5,
            help="Minimum font size for translated text",
        )
    
    # Translate button
    if st.button("🔄 Translate Document", type="primary", use_container_width=True):
        translate_document(
            uploaded_file,
            api_key,
            source_lang,
            target_lang,
            use_gpu,
            min_font_size,
        )
    
    # Show results
    if st.session_state.translation_complete and st.session_state.translated_pdf:
        st.divider()
        st.success("✅ Translation Complete!")
        
        # Show summary
        if st.session_state.summary:
            summary = st.session_state.summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Pages", summary.pages_processed)
            with col2:
                st.metric("Text Blocks", summary.text_blocks_translated)
            with col3:
                st.metric("Time", f"{summary.processing_time_seconds:.1f}s")
            
            if summary.errors:
                with st.expander(f"⚠️ Warnings ({len(summary.errors)})"):
                    for error in summary.errors:
                        st.warning(error)
        
        # Download button
        output_filename = uploaded_file.name.replace(".pdf", f"_{target_lang}.pdf")
        
        st.download_button(
            label="📥 Download Translated PDF",
            data=st.session_state.translated_pdf,
            file_name=output_filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )


def translate_document(
    uploaded_file,
    api_key: str,
    source_lang: str,
    target_lang: str,
    use_gpu: bool,
    min_font_size: float,
):
    """Translate the uploaded document."""
    # Reset state
    st.session_state.translated_pdf = None
    st.session_state.translation_complete = False
    st.session_state.summary = None
    
    # Create temp files
    with tempfile.TemporaryDirectory() as temp_dir:
        input_path = os.path.join(temp_dir, "input.pdf")
        output_path = os.path.join(temp_dir, "output.pdf")
        
        # Save uploaded file
        with open(input_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        
        # Create config
        config = TranslationConfig(
            target_language=target_lang,
            gemini_api_key=api_key,
            source_language=source_lang,
            use_gpu=use_gpu,
            min_font_size=min_font_size,
        )
        
        # Create translator
        translator = DocumentTranslator(config)
        
        # Progress indicators
        progress_bar = st.progress(0, text="Initializing...")
        status_text = st.empty()
        
        try:
            # Update progress
            status_text.text("📄 Parsing PDF...")
            progress_bar.progress(10, text="Parsing PDF...")
            
            # Translate
            status_text.text("🔍 Detecting language and extracting text...")
            progress_bar.progress(30, text="Extracting text...")
            
            summary = translator.translate_document(input_path, output_path)
            
            progress_bar.progress(90, text="Finalizing...")
            
            if summary.success:
                # Read output file
                with open(output_path, "rb") as f:
                    st.session_state.translated_pdf = f.read()
                
                st.session_state.translation_complete = True
                st.session_state.summary = summary
                
                progress_bar.progress(100, text="Complete!")
                status_text.empty()
            else:
                progress_bar.empty()
                status_text.empty()
                st.error(f"Translation failed: {', '.join(summary.errors)}")
                
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Error: {str(e)}")


if __name__ == "__main__":
    main()
