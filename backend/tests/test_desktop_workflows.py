import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
import pymupdf

from app.main import app
from app.services.assistant_service import answer_question
from app.services.comparison_service import extract_sections
from app.services.embedding_cache import cached_embed
from app.services.user_context import profile_directory


def pdf_bytes():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 60), "Methods\nWe used logistic regression on 120 leaf photographs.\nResults\nAccuracy was 81 percent.\nLimitations\nOnly one crop variety was evaluated.")
        return doc.tobytes()


class DesktopAccountTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.environment = patch.dict(os.environ, {"LITLENS_DATA_DIR": self.tmp.name, "LITLENS_DATABASE_PATH": ""})
        self.environment.start()
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.environment.stop()
        self.tmp.cleanup()

    async def account(self, name):
        r = await self.client.post("/auth/register", json={"username": name, "display_name": name, "password": "strong-password-123"})
        self.assertEqual(r.status_code, 201, r.text)
        token = r.json()["token"]
        self.client.headers["Authorization"] = "Bearer " + token
        r = await self.client.put("/settings", json={"provider": "local", "embeddings_enabled": False, "auto_analyze": True})
        self.assertEqual(r.status_code, 200)
        return token, r

    async def upload(self):
        r = await self.client.post("/library/upload?filename=test.pdf", content=pdf_bytes(), headers={"Content-Type": "application/pdf"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    async def test_accounts_isolate_papers_pages_analysis_exports_chat_and_settings(self):
        alice, _ = await self.account("alice")
        upload = await self.upload()
        paper = upload["paper_id"]
        analysis = upload["analysis"]["analysis_id"]
        report = await self.client.get("/analysis/" + analysis)
        self.assertEqual(report.json()["status"], "completed", report.text)
        self.assertIn("retrieval", report.json()["report"])
        asked = await self.client.post("/assistant/ask", json={"question": "What method was used?", "paper_ids": [paper]})
        self.assertEqual(asked.status_code, 200)
        self.assertEqual(len((await self.client.get("/assistant/history?paper_id=" + paper)).json()["turns"]), 2)
        await self.account("bob")
        self.assertEqual((await self.client.get("/library/papers")).json()["count"], 0)
        for url in [f"/library/papers/{paper}", f"/library/papers/{paper}/pages", f"/analysis/{analysis}", f"/analysis/{analysis}/export", f"/assistant/history?paper_id={paper}"]:
            self.assertEqual((await self.client.get(url)).status_code, 404, url)
        self.assertEqual((await self.client.delete(f"/library/papers/{paper}")).status_code, 404)
        self.assertEqual((await self.client.post("/assistant/ask", json={"question": "Methods?", "paper_ids": [paper]})).status_code, 404)
        self.client.headers["Authorization"] = "Bearer " + alice
        self.assertEqual((await self.client.get(f"/library/papers/{paper}")).status_code, 200)
        self.assertEqual((await self.client.get("/settings")).json()["provider"], "local")
        self.assertEqual((await self.client.delete(f"/library/papers/{paper}")).status_code, 200)
        self.assertEqual((await self.client.get(f"/analysis/{analysis}")).status_code, 404)

    async def test_metadata_delete_returns_success_and_missing_record_returns_404(self):
        await self.account("alice")
        saved = await self.client.post("/library/papers", json={"title": "Metadata", "authors": []})
        paper = saved.json()["paper"]["id"]
        self.assertEqual((await self.client.delete("/library/papers/" + paper)).status_code, 200)
        self.assertEqual((await self.client.delete("/library/papers/" + paper)).status_code, 404)

    async def test_login_logout_password_hashing_and_invalid_password(self):
        self.assertEqual((await self.client.get("/library/papers")).status_code, 401)
        await self.account("alice")
        bad = await self.client.post("/auth/login", json={"username": "alice", "password": "wrong-password-123"})
        self.assertEqual(bad.status_code, 401)
        await self.client.post("/auth/logout")
        self.assertEqual((await self.client.get("/library/papers")).status_code, 401)
        good = await self.client.post("/auth/login", json={"username": "ALICE", "password": "strong-password-123"})
        self.assertEqual(good.status_code, 200)
        db = sqlite3.connect(Path(self.tmp.name) / "accounts.sqlite3")
        try:
            hashed = db.execute("SELECT password_hash FROM users").fetchone()[0]
            self.assertNotEqual(hashed, "strong-password-123")
        finally:
            db.close()

    async def test_api_mode_requires_explicit_consent_and_never_returns_key(self):
        await self.account("alice")
        body = {"provider": "api", "api_url": "https://example.com/v1/chat/completions", "api_model": "model"}
        self.assertEqual((await self.client.put("/settings", json=body)).status_code, 422)
        body.update(allow_external_ai=True, api_key="test-secret-not-a-real-key")
        protected = b"encrypted-test-value"
        with patch("app.services.settings._crypt", return_value=protected):
            r = await self.client.put("/settings", json=body)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["has_api_key"])
        self.assertNotIn("test-secret", r.text)
        self.assertNotIn("api_key", (await self.client.get("/settings")).json())

    async def test_model_failure_still_finishes_automatic_report(self):
        await self.account("alice")
        await self.client.put("/settings", json={"provider": "ollama", "embeddings_enabled": False, "auto_analyze": True})
        with patch("app.services.ollama_provider.OllamaChat.complete", side_effect=RuntimeError("offline")):
            uploaded = await self.upload()
        report = (await self.client.get("/analysis/" + uploaded["analysis"]["analysis_id"])).json()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["report"]["analysis_mode"], "local_extractive")
        self.assertTrue(any("unavailable" in c for c in report["report"]["caveats"]))


class AccuracyRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_false_answer_when_model_abstains_or_invents_numeric_result(self):
        docs = [{"paper_id": "p", "chunk_id": "c", "title": "Test", "page_number": 1,
                 "text": "The method was evaluated on leaf photographs and achieved 81 percent accuracy."}]
        class LLM:
            def __init__(self, value): self.value = value
            async def complete(self, *_): return json.dumps(self.value)
        r = await answer_question("What clinical trial validated this method?", docs,
                                  llm_provider=LLM({"answerable": False, "claims": []}))
        self.assertEqual(r["answer_mode"], "abstain")
        invented = {"answerable": True, "claims": [{"text": "The accuracy was 99 percent.", "evidence_id": "E1", "quote": "achieved 81 percent accuracy"}]}
        r = await answer_question("What accuracy was achieved?", docs, llm_provider=LLM(invented))
        self.assertEqual(r["answer_mode"], "extractive")
        self.assertFalse(r["sufficient_evidence"])
        self.assertNotIn("99", r["answer"])

    async def test_embedding_cache_reuses_vectors_and_isolates_profiles(self):
        class Embedder:
            cache_key = "test/model"
            calls = 0
            async def embed(self, texts):
                self.calls += 1
                return [[1.0, 0.5] for _ in texts]
        provider = Embedder()
        with tempfile.TemporaryDirectory() as tmp:
            ctx = profile_directory.set(Path(tmp) / "alice")
            try:
                await cached_embed(provider, ["first", "second"])
                await cached_embed(provider, ["first", "second"])
                self.assertEqual(provider.calls, 1)
                profile_directory.set(Path(tmp) / "bob")
                await cached_embed(provider, ["first", "second"])
                self.assertEqual(provider.calls, 2)
            finally:
                profile_directory.reset(ctx)

    def test_comparison_keeps_section_continuations_and_stops_at_unrelated_heading(self):
        sections = extract_sections([
            {"page_number": 1, "text": "Methods\nWe used a classifier."},
            {"page_number": 2, "text": "We used five-fold validation.\nReferences\nUnrelated reference text."},
        ])
        self.assertIn("five-fold", sections["methods"]["text"])
        self.assertNotIn("Unrelated", sections["methods"]["text"])
        self.assertEqual(sections["methods"]["page_numbers"], [1, 2])
