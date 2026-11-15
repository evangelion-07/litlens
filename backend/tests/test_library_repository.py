import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pymupdf

from app.services.library_repository import (
    get_chunks,
    get_pages,
    get_paper,
    init_db,
    save_openalex_paper,
    save_uploaded_pdf,
)
from app.services.pdf_service import extract_pdf_pages


def make_pdf(text):
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    result = document.tobytes()
    document.close()
    return result


class LibraryRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_data_dir = os.environ.get("LITLENS_DATA_DIR")
        self.old_database_path = os.environ.get("LITLENS_DATABASE_PATH")
        os.environ["LITLENS_DATA_DIR"] = self.temp_dir.name
        os.environ.pop("LITLENS_DATABASE_PATH", None)

    def tearDown(self):
        if self.old_data_dir is None:
            os.environ.pop("LITLENS_DATA_DIR", None)
        else:
            os.environ["LITLENS_DATA_DIR"] = self.old_data_dir
        if self.old_database_path is None:
            os.environ.pop("LITLENS_DATABASE_PATH", None)
        else:
            os.environ["LITLENS_DATABASE_PATH"] = self.old_database_path
        self.temp_dir.cleanup()

    def test_saves_pdf_pages_and_page_aware_chunks(self):
        pdf = make_pdf("Research evidence stored with its source page.")
        pages = extract_pdf_pages(pdf)
        saved = save_uploaded_pdf("research-paper.pdf", pdf, pages)
        self.assertEqual(saved["processing_status"], "processed")
        self.assertEqual(saved["page_count"], 1)
        self.assertGreaterEqual(saved["chunk_count"], 1)
        self.assertTrue((Path(self.temp_dir.name) / "uploads" / f"{saved['paper_id']}.pdf").exists())
        self.assertEqual(get_pages(saved["paper_id"])[0]["page_number"], 1)
        chunks = get_chunks([saved["paper_id"]])
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]["page_number"], 1)
        self.assertEqual(chunks[0]["paper_id"], saved["paper_id"])
        self.assertEqual(get_paper(saved["paper_id"])["source_type"], "upload")

    def test_section_labels_are_saved_on_page_local_chunks(self):
        pdf = make_pdf("Methods\nWe use a convolutional model.\nResults\nRecall improves.")
        saved = save_uploaded_pdf("sectioned.pdf", pdf, extract_pdf_pages(pdf))
        chunks = get_chunks([saved["paper_id"]])
        self.assertEqual([item["section"] for item in chunks], ["methodology", "results"])
        self.assertEqual([item["page_number"] for item in chunks], [1, 1])

    def test_additive_migration_preserves_an_existing_library(self):
        database = Path(self.temp_dir.name) / "litlens.sqlite3"
        connection = sqlite3.connect(database)
        connection.executescript("""
            CREATE TABLE papers (
                id TEXT PRIMARY KEY, openalex_id TEXT, doi TEXT, title TEXT NOT NULL,
                authors_json TEXT NOT NULL, publication_year INTEGER, publication_type TEXT,
                cited_by_count INTEGER, abstract TEXT, open_access INTEGER NOT NULL DEFAULT 0,
                landing_page_url TEXT, pdf_url TEXT, source_type TEXT NOT NULL,
                original_filename TEXT, stored_pdf_path TEXT, processing_status TEXT NOT NULL,
                processing_message TEXT, page_count INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE pages (
                paper_id TEXT NOT NULL, page_number INTEGER NOT NULL, text TEXT NOT NULL,
                PRIMARY KEY (paper_id, page_number)
            );
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, page_number INTEGER NOT NULL,
                ordinal INTEGER NOT NULL, text TEXT NOT NULL
            );
            INSERT INTO papers (id, title, authors_json, source_type, processing_status, created_at)
            VALUES ('existing-paper', 'Existing paper', '[]', 'openalex', 'metadata_only', '2025-01-01');
            INSERT INTO pages (paper_id, page_number, text) VALUES ('existing-paper', 1, 'Existing page text.');
            INSERT INTO chunks (id, paper_id, page_number, ordinal, text)
            VALUES ('existing-chunk', 'existing-paper', 1, 0, 'Existing chunk text.');
        """)
        connection.close()

        init_db()
        self.assertEqual(get_paper("existing-paper")["title"], "Existing paper")
        self.assertEqual(get_pages("existing-paper")[0]["text"], "Existing page text.")
        migrated = get_chunks(["existing-paper"])
        self.assertEqual(migrated[0]["chunk_id"], "existing-chunk")
        connection = sqlite3.connect(database)
        paper_columns = {row[1] for row in connection.execute("PRAGMA table_info(papers)")}
        chunk_columns = {row[1] for row in connection.execute("PRAGMA table_info(chunks)")}
        analysis_tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        connection.close()
        self.assertIn("document_metadata_json", paper_columns)
        self.assertIn("section", chunk_columns)
        self.assertIn("paper_analyses", analysis_tables)

    def test_openalex_metadata_is_deduplicated_by_normalized_doi(self):
        first = save_openalex_paper({
            "title": "A paper",
            "openalex_id": "https://openalex.org/W1",
            "doi": "https://doi.org/10.1234/ABC",
            "authors": [],
            "open_access": False,
        })
        second = save_openalex_paper({
            "title": "A paper with metadata",
            "openalex_id": "https://openalex.org/W2",
            "doi": "10.1234/abc",
            "authors": ["A. Author"],
            "abstract": "Indexed abstract",
            "open_access": True,
        })
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["doi"], "10.1234/abc")
        self.assertEqual(second["abstract"], "Indexed abstract")
        self.assertTrue(second["open_access"])
        self.assertEqual(second["authors"], ["A. Author"])


if __name__ == "__main__":
    unittest.main()
