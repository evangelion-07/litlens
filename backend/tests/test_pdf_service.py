import os
import unittest
from unittest.mock import patch

import pymupdf

from app.services.pdf_service import InvalidPdfError, chunk_page_text, extract_pdf_document, extract_pdf_pages


def make_pdf(page_texts, metadata=None):
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    if metadata:
        document.set_metadata(metadata)
    result = document.tobytes()
    document.close()
    return result


class PdfExtractionTests(unittest.TestCase):
    def test_extracts_text_separately_for_each_page(self):
        pages = extract_pdf_pages(make_pdf(["Evidence on page one.", "Evidence on page two."]))
        self.assertEqual(len(pages), 2)
        self.assertIn("page one", pages[0])
        self.assertIn("page two", pages[1])

    def test_text_empty_pdf_is_reported_as_empty_page_text(self):
        self.assertEqual(extract_pdf_pages(make_pdf([""])), [""])

    def test_extracts_metadata_and_detectable_table_text(self):
        source = make_pdf(
            ["A readable page with a small table."],
            {"title": "Metadata title", "author": "Example Author"},
        )
        with patch("app.services.pdf_service._extract_tables", return_value=["[Extracted table 1]\nModel | Score"]):
            result = extract_pdf_document(source)
        self.assertEqual(result["metadata"]["title"], "Metadata title")
        self.assertEqual(result["metadata"]["author"], "Example Author")
        self.assertEqual(result["table_count"], 1)
        self.assertIn("[Extracted table 1]", result["page_texts"][0])

    def test_reports_ocr_disabled_separately_from_missing_tesseract(self):
        with patch.dict(os.environ, {"LITLENS_ENABLE_OCR": "false"}):
            with patch("app.services.pdf_service._tesseract_available", return_value=True):
                result = extract_pdf_document(make_pdf([""]))
        self.assertTrue(result["tesseract_available"])
        self.assertFalse(result["ocr_enabled"])
        self.assertFalse(result["ocr_available"])

    def test_rejects_invalid_pdf_bytes(self):
        with self.assertRaises(InvalidPdfError):
            extract_pdf_pages(b"not a pdf")

    def test_chunks_overlap_and_remain_bounded(self):
        text = " ".join(f"token{i}" for i in range(200))
        chunks = chunk_page_text(text, chunk_size=120, overlap=20)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(0 < len(chunk) <= 120 for chunk in chunks))
        combined = " ".join(chunks)
        for index in range(200):
            self.assertIn(f"token{index}", combined)


if __name__ == "__main__":
    unittest.main()

