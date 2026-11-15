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
    page.insert_textbox(pymupdf.Rect(72, 72, 520, 720), text)
    result = document.tobytes()
    document.close()
    return result


class ComparisonApiTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_compares_selected_pdfs_and_returns_evidence_based_gaps(self):
        first = await self.client.post(
            "/library/upload",
            params={"filename": "paper-one.pdf"},
            content=make_pdf("Methods\nA convolutional model was evaluated.\nLimitations\nThe study uses a small field sample."),
            headers={"content-type": "application/pdf"},
        )
        second = await self.client.post(
            "/library/upload",
            params={"filename": "paper-two.pdf"},
            content=make_pdf("Methods\nA random forest model was evaluated.\nFuture Work\nTest the method across regions."),
            headers={"content-type": "application/pdf"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 200, second.text)

        response = await self.client.post(
            "/library/compare",
            json={"paper_ids": [first.json()["paper_id"], second.json()["paper_id"]]},
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result["papers"]), 2)
        self.assertEqual(result["papers"][0]["sections"]["methods"]["page_numbers"], [1])
        self.assertEqual(len(result["reported_limitations"]), 1)
        self.assertGreaterEqual(len(result["potential_gaps"]), 2)
        self.assertEqual(result["potential_gaps"][0]["confidence"], "low")
        self.assertIn("not establish global novelty", result["potential_gaps"][0]["scope_note"])


if __name__ == "__main__":
    unittest.main()
