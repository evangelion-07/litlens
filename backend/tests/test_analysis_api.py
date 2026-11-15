from api_support import authenticate_test
import asyncio
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
    data = document.tobytes()
    document.close()
    return data


class AnalysisApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LITLENS_DATA_DIR")
        self.old_database_path = os.environ.get("LITLENS_DATABASE_PATH")
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
        if self.old_database_path is None:
            os.environ.pop("LITLENS_DATABASE_PATH", None)
        else:
            os.environ["LITLENS_DATABASE_PATH"] = self.old_database_path
        self.temp_dir.cleanup()

    async def test_paper_analysis_is_persisted_and_exports_keep_citations(self):
        upload = await self.client.post(
            "/library/upload",
            params={"filename": "analysis-study.pdf"},
            content=make_pdf(
                "Results\nThe proposed retrieval method improves recall on the test collection. "
                "The authors report no confidence intervals."
            ),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(upload.status_code, 200, upload.text)
        paper_id = upload.json()["paper_id"]

        started = await self.client.post(
            "/analysis/papers/" + paper_id,
            json={"use_external_ai": False},
        )
        self.assertEqual(started.status_code, 202, started.text)
        analysis_id = started.json()["analysis_id"]

        current = None
        for _ in range(20):
            response = await self.client.get("/analysis/" + analysis_id)
            self.assertEqual(response.status_code, 200, response.text)
            current = response.json()
            if current["status"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.03)

        self.assertEqual(current["status"], "completed", current)
        self.assertEqual(current["report"]["coverage"]["scope"], "full_text")
        self.assertTrue(current["report"]["evidence"])
        self.assertEqual(current["report"]["evidence"][0]["page_number"], 1)

        markdown = await self.client.get(
            "/analysis/" + analysis_id + "/export",
            params={"format": "markdown"},
        )
        self.assertEqual(markdown.status_code, 200, markdown.text)
        self.assertIn("[E1]", markdown.text)

        pdf = await self.client.get(
            "/analysis/" + analysis_id + "/export",
            params={"format": "pdf"},
        )
        self.assertEqual(pdf.status_code, 200, pdf.text[:200])
        self.assertTrue(pdf.content.startswith(b"%PDF"))

        history = await self.client.get("/analysis/history")
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()[0]["analysis_id"], analysis_id)
        self.assertIsNone(history.json()[0]["report"])

    async def test_external_ai_requires_configured_provider(self):
        old_url = os.environ.pop("LLM_API_URL", None)
        old_model = os.environ.pop("LLM_MODEL", None)
        try:
            saved = await self.client.post(
                "/library/papers",
                json={"title": "Metadata Only", "authors": [], "open_access": False},
            )
            paper_id = saved.json()["paper"]["id"]
            response = await self.client.post(
                "/analysis/papers/" + paper_id,
                json={"use_external_ai": True},
            )
            self.assertEqual(response.status_code, 422)
            self.assertIn("No AI model", response.json()["detail"])
        finally:
            if old_url is not None:
                os.environ["LLM_API_URL"] = old_url
            if old_model is not None:
                os.environ["LLM_MODEL"] = old_model


if __name__ == "__main__":
    unittest.main()
