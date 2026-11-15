from api_support import authenticate_test
import os
import tempfile
import unittest

import pymupdf
from httpx import ASGITransport, AsyncClient

from app.main import app


def make_pdf(text):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


class AssistantApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LITLENS_DATA_DIR")
        os.environ["LITLENS_DATA_DIR"] = self.temp_dir.name
        os.environ.pop("LITLENS_DATABASE_PATH", None)
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        await authenticate_test(self)

    async def asyncTearDown(self):
        await self.client.aclose()
        if self.old_data_dir is None:
            os.environ.pop("LITLENS_DATA_DIR", None)
        else:
            os.environ["LITLENS_DATA_DIR"] = self.old_data_dir
        self.temp_dir.cleanup()

    async def test_question_answer_returns_page_citation(self):
        upload = await self.client.post(
            "/library/upload",
            params={"filename": "method-study.pdf"},
            content=make_pdf("This study uses logistic regression as its classification method."),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        paper_id = upload.json()["paper_id"]
        response = await self.client.post(
            "/assistant/ask",
            json={"question": "What classification method was used?", "paper_ids": [paper_id]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["sufficient_evidence"])
        self.assertEqual(result["citations"][0]["paper_id"], paper_id)
        self.assertEqual(result["citations"][0]["page_number"], 1)

    async def test_unmatched_question_abstains(self):
        response = await self.client.post(
            "/assistant/ask",
            json={"question": "What does the paper say about quantum cryptography?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answer_mode"], "abstain")
        self.assertEqual(response.json()["citations"], [])

    async def test_question_validation_rejects_blank_input(self):
        response = await self.client.post("/assistant/ask", json={"question": "   "})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
