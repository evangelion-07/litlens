from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.services.document_structure import split_page_sections


class InvalidPdfError(ValueError):
    """The uploaded bytes could not be read as a supported PDF."""


class PdfPasswordError(InvalidPdfError):
    """The uploaded PDF is encrypted and no password workflow is configured."""


class PdfDependencyMissing(RuntimeError):
    """PyMuPDF is not installed in the active Python environment."""


def _pymupdf_module() -> Any:
    try:
        import pymupdf
        return pymupdf
    except ImportError:
        try:
            import fitz
            return fitz
        except ImportError as exc:
            raise PdfDependencyMissing(
                "PDF extraction requires PyMuPDF. Install backend requirements with: "
                "python -m pip install -r requirements.txt"
            ) from exc


def _ocr_enabled() -> bool:
    return os.getenv("LITLENS_ENABLE_OCR", "true").strip().casefold() not in {
        "0", "false", "no", "off",
    }


def _tesseract_available(pymupdf: Any) -> bool:
    configured = os.getenv("LITLENS_TESSERACT_PATH", "").strip()
    if configured:
        executable = Path(configured)
        if executable.is_file():
            tools = getattr(pymupdf, "TOOLS", None)
            setter = getattr(tools, "set_tesseract_path", None)
            if callable(setter):
                try:
                    setter(str(executable))
                    return True
                except Exception:
                    return False
    return bool(shutil.which("tesseract"))


def _extract_tables(page: Any) -> list[str]:
    finder = getattr(page, "find_tables", None)
    if not callable(finder):
        return []
    try:
        found = finder()
        tables = getattr(found, "tables", []) or []
    except Exception:
        return []

    rendered: list[str] = []
    for table_number, table in enumerate(tables, start=1):
        try:
            rows = table.extract() or []
        except Exception:
            continue
        lines = []
        for row in rows:
            cells = [" ".join(str(cell or "").split()) for cell in row]
            if any(cells):
                lines.append(" | ".join(cells))
        if lines:
            rendered.append(f"[Extracted table {table_number}]\n" + "\n".join(lines))
    return rendered


def extract_pdf_document(pdf_bytes: bytes) -> dict[str, Any]:
    """Extract page text, detectable table text, PDF metadata, and optional OCR status."""
    if not isinstance(pdf_bytes, bytes) or not pdf_bytes:
        raise InvalidPdfError("The uploaded file is empty.")

    pymupdf = _pymupdf_module()
    document = None
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        if getattr(document, "is_encrypted", False) or getattr(document, "needs_pass", False):
            raise PdfPasswordError("Password-protected PDFs are not supported.")
        if len(document) < 1:
            raise InvalidPdfError("The PDF does not contain any pages.")
        if len(document) > 500:
            raise InvalidPdfError("This document exceeds the 500-page processing limit. Split it into smaller PDFs.")

        raw_metadata = getattr(document, "metadata", None) or {}
        metadata = {
            key: str(raw_metadata.get(key) or "").strip()
            for key in ("title", "author", "subject", "keywords", "creationDate")
            if str(raw_metadata.get(key) or "").strip()
        }

        ocr_enabled = _ocr_enabled()
        tesseract_available = _tesseract_available(pymupdf)
        ocr_available = ocr_enabled and tesseract_available
        ocr_language = os.getenv("LITLENS_OCR_LANGUAGE", "eng").strip() or "eng"
        page_texts: list[str] = []
        ocr_page_numbers: list[int] = []
        ocr_failed_pages: list[int] = []
        table_count = 0

        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if ocr_available and len(text) < 40:
                try:
                    textpage = page.get_textpage_ocr(full=True, language=ocr_language)
                    ocr_text = page.get_text("text", textpage=textpage).strip()
                    if len(ocr_text) > len(text):
                        text = ocr_text
                        ocr_page_numbers.append(page_number)
                except Exception:
                    ocr_failed_pages.append(page_number)

            tables = _extract_tables(page) if text else []
            table_count += len(tables)
            if tables:
                text = "\n\n".join(part for part in (text, *tables) if part)

            page_texts.append(text)

        return {
            "page_texts": page_texts,
            "metadata": metadata,
            "ocr_available": ocr_available,
            "ocr_enabled": ocr_enabled,
            "tesseract_available": tesseract_available,
            "ocr_page_numbers": ocr_page_numbers,
            "ocr_failed_pages": ocr_failed_pages,
            "table_count": table_count,
            "page_count": len(page_texts),
        }
    except InvalidPdfError:
        raise
    except Exception as exc:
        raise InvalidPdfError("Could not read the PDF. It may be invalid or damaged.") from exc
    finally:
        if document is not None:
            document.close()


def extract_pdf_pages(pdf_bytes: bytes) -> list[str]:
    """Compatibility helper returning one extracted text string per PDF page."""
    return extract_pdf_document(pdf_bytes)["page_texts"]


def chunk_page_text(text: str, chunk_size: int = 1100, overlap: int = 150) -> list[str]:
    """Split one page into overlapping text chunks without crossing page boundaries."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    if chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            preferred_break = normalized.rfind(" ", start + (chunk_size * 2 // 3), end)
            if preferred_break > start:
                end = preferred_break
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks
