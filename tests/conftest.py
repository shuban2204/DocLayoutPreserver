"""Pytest configuration and shared fixtures."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models.data_models import BoundingBox, TextBlock, FontInfo, PageContent, ImageRegion
from models.config import TranslationConfig


@pytest.fixture
def sample_bbox():
    """Create a sample bounding box."""
    return BoundingBox(x0=10.0, y0=20.0, x1=100.0, y1=50.0)


@pytest.fixture
def sample_font_info():
    """Create sample font information."""
    return FontInfo(name="Arial", size=12.0, color=(0, 0, 0), is_bold=False, is_italic=False)


@pytest.fixture
def sample_text_block(sample_bbox, sample_font_info):
    """Create a sample text block."""
    return TextBlock(
        text="Sample text",
        bbox=sample_bbox,
        font_name="Arial",
        font_size=12.0,
        page_number=0,
        font_info=sample_font_info,
    )


@pytest.fixture
def sample_config():
    """Create a sample translation config."""
    return TranslationConfig(
        target_language="es",
        gemini_api_key="test-api-key",
        use_gpu=False,
        batch_size=5,
    )


@pytest.fixture
def sample_page_content(sample_text_block):
    """Create sample page content."""
    return PageContent(
        page_number=0,
        width=612.0,
        height=792.0,
        text_blocks=[sample_text_block],
        image_regions=[],
    )
