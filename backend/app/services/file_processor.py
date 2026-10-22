"""
File Processor — Multi-Format Text Extraction
═══════════════════════════════════════════════════════════════════════════════

Supported formats  →  extraction method
────────────────────────────────────────
.pdf               →  pdfplumber (layout-aware; handles tables and columns)
.docx              →  python-docx (paragraphs + tables, preserves structure)
.txt / .md         →  direct UTF-8 read
.png / .jpg / .jpeg→  pytesseract OCR (Tesseract v5)

Design Decisions:
• pdfplumber over PyPDF2:  PyPDF2 mangles whitespace on multi-column PDFs.
  pdfplumber uses pdfminer under the hood with better layout analysis.
• pytesseract Tesseract:   PSM 3 (fully automatic page segmentation) works
  for most scanned docs.  Falls back to PSM 6 if too little text returned.
• Async wrapper:  all CPU-bound file ops run in executor so FastAPI's event
  loop never blocks.
• Size guard:  reject files > MAX_SIZE_MB before any processing.
"""

import io
import re
import asyncio
import logging
from pathlib import Path
from typing import Union

from app.config import settings

logger = logging.getLogger(__name__)

MAX_BYTES = settings.max_file_size_mb * 1024 * 1024


def _clean_text(raw: str) -> str:
    """
    Post-extraction text cleaning:
    1. Remove non-printable control chars (except \n \t)
    2. Collapse 4+ consecutive blank lines → 2 blank lines
    3. Strip leading / trailing whitespace
    """
    raw = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", " ", raw)
    raw = re.sub(r"\n{4,}", "\n\n\n", raw)
    raw = re.sub(r" {3,}", " ", raw)
    return raw.strip()


def _extract_from_pdf_bytes(data: bytes) -> str:
    """
    pdfplumber extraction.
    Iterates pages; extracts text with layout heuristics, then tables as
    TSV rows so tabular data (invoice line items) survives intact.
    """
    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber not installed. Run: pip install pdfplumber"
        )

    parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        logger.info(f"PDF has {len(pdf.pages)} page(s)")
        for page_num, page in enumerate(pdf.pages, 1):
            # Extract text first
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            parts.append(f"--- Page {page_num} ---")
            if text:
                parts.append(text)

            # Extract tables (invoice rows, experience tables, etc.)
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    cleaned_row = [cell.strip() if cell else "" for cell in row]
                    parts.append("\t".join(cleaned_row))

    return _clean_text("\n".join(parts))


def _extract_from_docx_bytes(data: bytes) -> str:
    """
    python-docx extraction.
    Walks paragraphs (including heading levels) then tables.
    """
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError(
            "python-docx not installed. Run: pip install python-docx"
        )

    doc = Document(io.BytesIO(data))
    parts: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            parts.append(text)

    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            parts.append("\t".join(cells))

    return _clean_text("\n".join(parts))


def _extract_from_image_bytes(data: bytes) -> str:
    """
    Tesseract OCR via pytesseract.
    PSM 3 = auto page seg (default, best for mixed content).
    If result is suspiciously short, retry with PSM 6 (single block).
    """
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        raise RuntimeError(
            "Pillow / pytesseract not installed. "
            "Run: pip install Pillow pytesseract  (and install Tesseract binary)"
        )

    img = Image.open(io.BytesIO(data))

    # Enhance for better OCR accuracy
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    config_psm3 = "--oem 3 --psm 3"
    text = pytesseract.image_to_string(img, config=config_psm3)

    if len(text.strip()) < 50:
        # Retry with block-level segmentation
        logger.info("PSM 3 yielded little text — retrying with PSM 6")
        config_psm6 = "--oem 3 --psm 6"
        text = pytesseract.image_to_string(img, config=config_psm6)

    return _clean_text(text)


def _sync_process(filename: str, data: bytes) -> str:
    """Dispatch to the right extractor based on file extension (runs in thread)."""
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _extract_from_pdf_bytes(data)
    elif ext == ".docx":
        return _extract_from_docx_bytes(data)
    elif ext in (".txt", ".md", ".csv", ".log"):
        return _clean_text(data.decode("utf-8", errors="replace"))
    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"):
        return _extract_from_image_bytes(data)
    else:
        raise ValueError(
            f"Unsupported file type: '{ext}'. "
            f"Supported: {', '.join(settings.supported_extensions)}"
        )


async def process_file(filename: str, content: bytes) -> str:
    """
    Async entry-point — offloads blocking CPU work to thread pool.

    Args:
        filename: Original file name (used for extension detection + logging)
        content:  Raw file bytes

    Returns:
        Cleaned, extracted text string

    Raises:
        ValueError: Unsupported format or file too large
        RuntimeError: Missing optional dependency (pdfplumber, docx, etc.)
    """
    if len(content) == 0:
        raise ValueError("Uploaded file is empty")

    if len(content) > MAX_BYTES:
        size_mb = len(content) / (1024 * 1024)
        raise ValueError(
            f"File too large: {size_mb:.1f} MB (max {settings.max_file_size_mb} MB)"
        )

    logger.info(f"Processing file '{filename}' ({len(content):,} bytes)…")

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(None, _sync_process, filename, content)

    if not text or not text.strip():
        raise ValueError(
            f"No text could be extracted from '{filename}'. "
            "The file may be empty, image-only (without OCR support), or corrupted."
        )

    logger.info(f"Extracted {len(text):,} chars from '{filename}'")
    return text
