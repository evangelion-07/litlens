from api_support import authenticate_test
import os
import tempfile
import unittest

import pymupdf
from httpx import ASGITransport, AsyncClient

from app.main import app


def make_pdf(page_texts):
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


class LibraryApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LITLENS_DATA_DIR")
        self.old_database_path = os.environ.get("LITLENS_DATABASE_PATH")
        self.old_upload_limit = os.environ.get("LITLENS_MAX_UPLOAD_MB")
        os.environ["LITLENS_DATA_DIR"] = self.temp_dir.name
        os.environ.pop("LITLENS_DATABASE_PATH", None)
        os.environ["LITLENS_MAX_UPLOAD_MB"] = "1"
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await authenticate_test(self)

    async def asyncTearDown(self):
        await self.client.aclose()
        for name, old_value in (
            ("LITLENS_DATA_DIR", self.old_data_dir),
            ("LITLENS_DATABASE_PATH", self.old_database_path),
            ("LITLENS_MAX_UPLOAD_MB", self.old_upload_limit),
        ):
            if old_value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = old_value
        self.temp_dir.cleanup()

    async def test_upload_extracts_and_returns_page_provenance(self):
        response = await self.client.post(
            "/library/upload",
            params={"filename": "two-pages.pdf"},
            content=make_pdf(["First page has methods.", "Second page reports results."]),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result["processing_status"], "processed")
        self.assertEqual(result["page_count"], 2)

        pages_response = await self.client.get(f"/library/papers/{result['paper_id']}/pages")
        self.assertEqual(pages_response.status_code, 200)
        pages = pages_response.json()["pages"]
        self.assertEqual([page["page_number"] for page in pages], [1, 2])
        self.assertIn("methods", pages[0]["text"])
        self.assertIn("results", pages[1]["text"])

    async def test_text_empty_pdf_is_stored_with_clear_status(self):
        response = await self.client.post(
            "/library/upload",
            params={"filename": "scan.pdf"},
            content=make_pdf([""]),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["processing_status"], "no_text")
        self.assertEqual(response.json()["chunk_count"], 0)
        self.assertTrue(response.json()["processing_message"])
        self.assertTrue(any(word in response.json()["processing_message"] for word in ("Tesseract", "OCR", "readable text")))

    async def test_rejects_wrong_type_and_over_limit_uploads(self):
        response = await self.client.post(
            "/library/upload",
            params={"filename": "note.txt"},
            content=b"not a pdf",
            headers={"content-type": "text/plain"},
        )
        self.assertEqual(response.status_code, 415)

        response = await self.client.post(
            "/library/upload",
            params={"filename": "large.pdf"},
            content=b"%PDF-" + (b"0" * (1024 * 1024)),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()
