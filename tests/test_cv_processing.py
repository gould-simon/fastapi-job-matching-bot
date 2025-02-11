import pytest
from app.cv_processor import process_cv, extract_cv_text, generate_cv_embedding
import os
from pathlib import Path
import logging
import shutil
from typing import Generator
import pytest_asyncio
from docx import Document
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# Setup logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture
def sample_cv_pdf(temp_dir: Path) -> Path:
    """Create a sample PDF CV for testing."""
    cv_path = temp_dir / "test_cv.pdf"
    c = canvas.Canvas(str(cv_path), pagesize=letter)
    c.drawString(100, 750, "John Doe")
    c.drawString(100, 730, "Senior Audit Manager")
    c.drawString(100, 710, "10+ years of experience")
    c.drawString(100, 690, "EXPERIENCE")
    c.drawString(100, 670, "Senior Audit Manager at Big4 Firm")
    c.save()
    return cv_path


@pytest.fixture
def sample_cv_docx(temp_dir: Path) -> Generator[Path, None, None]:
    """Provide path to test DOCX CV.

    Args:
        temp_dir: Temporary directory for test files

    Returns:
        Path to test DOCX file
    """
    cv_path = temp_dir / "test_cv.docx"
    # Copy test file to temp directory
    shutil.copy(
        os.path.join(os.path.dirname(__file__), "test_files", "test_cv.docx"), cv_path
    )
    yield cv_path


@pytest.fixture
def corrupt_pdf(temp_dir: Path) -> Path:
    """Create a corrupt PDF file for testing."""
    pdf_path = temp_dir / "corrupt.pdf"
    with open(pdf_path, "wb") as f:
        f.write(b"Not a valid PDF file")
    return pdf_path


@pytest.mark.asyncio
async def test_process_cv(sample_cv_pdf: Path):
    """Test complete CV processing pipeline."""
    # Process the CV
    cv_text, cv_embedding = await process_cv(str(sample_cv_pdf))

    # Verify text extraction
    assert cv_text, "Extracted text should not be empty"
    assert "John Doe" in cv_text, "Should extract basic content"
    assert "Senior Audit Manager" in cv_text, "Should extract job title"

    # Verify embedding
    assert len(cv_embedding) > 0, "Embedding should not be empty"
    assert all(
        isinstance(x, float) for x in cv_embedding
    ), "Embedding should contain floats"


@pytest.mark.asyncio
async def test_extract_cv_text_pdf(sample_cv_pdf: Path):
    """Test CV text extraction from PDF."""
    cv_text = await extract_cv_text(str(sample_cv_pdf))

    # Check content
    assert cv_text is not None
    assert len(cv_text) > 0
    assert "John Doe" in cv_text
    assert "Senior Audit Manager" in cv_text
    assert "EXPERIENCE" in cv_text
    assert "Senior Audit Manager at Big4 Firm" in cv_text

    # Check text cleaning
    assert "\x00" not in cv_text  # No null bytes
    assert not cv_text.startswith(" ")  # No leading spaces
    assert not cv_text.endswith(" ")  # No trailing spaces
    assert "  " not in cv_text  # No double spaces


@pytest.mark.asyncio
async def test_extract_cv_text_docx(sample_cv_docx: Path):
    """Test CV text extraction from DOCX."""
    cv_text = await extract_cv_text(str(sample_cv_docx))

    # Check content
    assert cv_text is not None
    assert len(cv_text) > 0
    assert "John Doe" in cv_text
    assert "Senior Audit Manager" in cv_text
    assert "EXPERIENCE" in cv_text
    assert "Senior Audit Manager at Big4 Firm" in cv_text

    # Check text cleaning
    assert "\x00" not in cv_text  # No null bytes
    assert not cv_text.startswith(" ")  # No leading spaces
    assert not cv_text.endswith(" ")  # No trailing spaces
    assert "  " not in cv_text  # No double spaces


@pytest.mark.asyncio
async def test_generate_cv_embedding():
    """Test CV embedding generation."""
    test_cases = [
        # Normal case
        """
        JOHN DOE
        Senior Audit Manager with 10+ years of experience
        Expert in technology audits and team leadership
        """,
        # Very long text
        "A" * 10000,
        # Special characters
        "🚀 John's CV (2024) - £100k+ roles",
        # Multiple languages
        """
        JOHN DOE
        Senior Audit Manager
        工程师 (Engineer)
        """,
    ]

    for test_text in test_cases:
        embedding = await generate_cv_embedding(test_text)

        assert embedding is not None
        assert len(embedding) == 1536
        assert all(
            isinstance(x, float) for x in embedding
        ), "Embedding should contain floats"
        assert all(-1 <= x <= 1 for x in embedding)

    # Test empty text
    with pytest.raises(ValueError) as exc_info:
        await generate_cv_embedding("")
    assert "Cannot generate embedding for empty text" in str(exc_info.value)

    # Test whitespace-only text
    with pytest.raises(ValueError) as exc_info:
        await generate_cv_embedding("   \n   \t   ")
    assert "Cannot generate embedding for empty text" in str(exc_info.value)


@pytest.mark.asyncio
async def test_process_cv_error_handling(corrupt_pdf: Path, temp_dir: Path):
    """Test error handling in CV processing."""
    # Test with non-existent file
    with pytest.raises(FileNotFoundError) as exc_info:
        await process_cv("non_existent_file.pdf")
    assert "system cannot find the file" in str(exc_info.value).lower()

    # Test with corrupt PDF
    with pytest.raises(Exception) as exc_info:
        await process_cv(str(corrupt_pdf))
    assert "No /Root object!" in str(exc_info.value)  # Updated to match actual error

    # Test with unsupported file type
    test_txt_path = temp_dir / "test.txt"
    with open(test_txt_path, "w") as f:
        f.write("Test content")

    with pytest.raises(ValueError) as exc_info:
        await process_cv(str(test_txt_path))
    assert "Unsupported file format" in str(exc_info.value)  # Updated assertion

    # Test with empty file
    empty_pdf = temp_dir / "empty.pdf"
    with open(empty_pdf, "wb") as f:
        pass  # Create empty file

    with pytest.raises(ValueError) as exc_info:
        await process_cv(str(empty_pdf))
    assert "Empty or invalid file" in str(exc_info.value)  # Updated assertion

    # Test with empty DOCX
    empty_docx = temp_dir / "empty.docx"
    Document().save(empty_docx)

    with pytest.raises(ValueError) as exc_info:
        await process_cv(str(empty_docx))
    assert "Empty or invalid file" in str(exc_info.value)  # Updated assertion

    # Test with very large file
    large_pdf = temp_dir / "large.pdf"
    with open(large_pdf, "wb") as f:
        f.write(b"%PDF-1.4" + b"0" * (10 * 1024 * 1024))  # 10MB file

    with pytest.raises(ValueError) as exc_info:
        await process_cv(str(large_pdf))
    assert "File too large" in str(exc_info.value)


@pytest.mark.asyncio
async def test_cv_text_extraction(sample_cv_pdf: Path, sample_cv_docx: Path):
    """Test CV text extraction from different file formats."""
    # Test PDF extraction
    pdf_text = await extract_cv_text(str(sample_cv_pdf))
    assert pdf_text, "PDF text extraction should not return empty string"
    assert not pdf_text.startswith("\x00"), "PDF text should not contain null bytes"
    assert (
        pdf_text.strip() == pdf_text
    ), "PDF text should not have leading/trailing spaces"

    # Test DOCX extraction
    docx_text = await extract_cv_text(str(sample_cv_docx))
    assert docx_text, "DOCX text extraction should not return empty string"
    assert not docx_text.startswith("\x00"), "DOCX text should not contain null bytes"
    assert (
        docx_text.strip() == docx_text
    ), "DOCX text should not have leading/trailing spaces"


@pytest.mark.asyncio
async def test_cv_embedding_generation():
    """Test CV embedding generation with various edge cases."""
    # Test with normal text
    normal_text = "Software engineer with 5 years of experience in Python and FastAPI"
    normal_embedding = await generate_cv_embedding(normal_text)
    assert len(normal_embedding) > 0, "Embedding should not be empty"
    assert all(
        isinstance(x, float) for x in normal_embedding
    ), "Embedding should contain floats"

    # Test with empty text
    with pytest.raises(ValueError) as exc_info:
        await generate_cv_embedding("")
    assert "Cannot generate embedding for empty text" in str(exc_info.value)

    # Test with whitespace-only text
    with pytest.raises(ValueError) as exc_info:
        await generate_cv_embedding("   \n   \t   ")
    assert "Cannot generate embedding for empty text" in str(exc_info.value)

    # Test with very long text
    long_text = "A" * 10000
    long_embedding = await generate_cv_embedding(long_text)
    assert len(long_embedding) > 0, "Should handle long text"
    assert len(long_embedding) == len(
        normal_embedding
    ), "Embedding dimension should be consistent"

    # Test with special characters
    special_text = "🚀 John's CV (2024) - £100k+ roles"
    special_embedding = await generate_cv_embedding(special_text)
    assert len(special_embedding) > 0, "Should handle special characters"
    assert len(special_embedding) == len(
        normal_embedding
    ), "Embedding dimension should be consistent"
