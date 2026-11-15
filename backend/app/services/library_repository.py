from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.document_structure import split_page_sections
from app.services.openalex_service import normalize_doi
from app.services.pdf_service import chunk_page_text
from app.services.user_context import profile_directory

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def data_dir() -> Path:
    if profile_directory.get() is not None:
        return profile_directory.get()
    configured = os.getenv("LITLENS_DATA_DIR")
    path = Path(configured).expanduser() if configured else PROJECT_ROOT / "data"
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def database_path() -> Path:
    if profile_directory.get() is not None:
        return data_dir() / "litlens.sqlite3"
    configured = os.getenv("LITLENS_DATABASE_PATH")
    path = Path(configured).expanduser() if configured else data_dir() / "litlens.sqlite3"
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def _connection():
    connection = _connect()
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with _connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS papers (
                id TEXT PRIMARY KEY,
                openalex_id TEXT,
                doi TEXT,
                title TEXT NOT NULL,
                authors_json TEXT NOT NULL DEFAULT '[]',
                publication_year INTEGER,
                publication_type TEXT,
                cited_by_count INTEGER,
                abstract TEXT,
                open_access INTEGER NOT NULL DEFAULT 0,
                landing_page_url TEXT,
                pdf_url TEXT,
                source_type TEXT NOT NULL,
                original_filename TEXT,
                stored_pdf_path TEXT,
                processing_status TEXT NOT NULL,
                processing_message TEXT,
                document_metadata_json TEXT NOT NULL DEFAULT '{}',
                page_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_papers_openalex_id ON papers(openalex_id);

            CREATE TABLE IF NOT EXISTS pages (
                paper_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                text TEXT NOT NULL,
                PRIMARY KEY (paper_id, page_number),
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                ordinal INTEGER NOT NULL,
                section TEXT,
                text TEXT NOT NULL,
                FOREIGN KEY (paper_id, page_number)
                    REFERENCES pages(paper_id, page_number) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_paper_page
                ON chunks(paper_id, page_number, ordinal);

            CREATE TABLE IF NOT EXISTS paper_analyses (
                id TEXT PRIMARY KEY,
                paper_id TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress INTEGER NOT NULL DEFAULT 0,
                report_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_paper_analyses_paper_created
                ON paper_analyses(paper_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS chat_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
                role TEXT NOT NULL, content TEXT NOT NULL, details TEXT NOT NULL DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_chat_paper ON chat_turns(paper_id, id);
            """
        )
        # Non-destructive schema extensions for databases created by the earlier MVP.
        for table, column, declaration in (
            ("papers", "document_metadata_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("chunks", "section", "TEXT"),
        ):
            existing = {
                row["name"]
                for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
                )


def _decode_paper(row: sqlite3.Row) -> dict[str, Any]:
    paper = dict(row)
    paper["authors"] = json.loads(paper.pop("authors_json") or "[]")
    paper["document_metadata"] = json.loads(
        paper.pop("document_metadata_json", "{}") or "{}"
    )
    paper["open_access"] = bool(paper["open_access"])
    return paper


def list_papers() -> list[dict[str, Any]]:
    init_db()
    with _connection() as connection:
        rows = connection.execute(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM pages pg WHERE pg.paper_id = p.id) AS stored_page_count,
                   (SELECT COUNT(*) FROM chunks c WHERE c.paper_id = p.id) AS chunk_count,
                   (SELECT COUNT(*) FROM paper_analyses a WHERE a.paper_id = p.id) AS analysis_count,
                   (SELECT status FROM paper_analyses a WHERE a.paper_id = p.id
                    ORDER BY a.created_at DESC LIMIT 1) AS latest_analysis_status
            FROM papers p
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    return [_decode_paper(row) for row in rows]


def get_paper(paper_id: str) -> dict[str, Any] | None:
    init_db()
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
    return _decode_paper(row) if row else None


def save_openalex_paper(paper: Mapping[str, Any]) -> dict[str, Any]:
    """Save search metadata, merging with an existing DOI/OpenAlex record if found."""
    init_db()
    doi = normalize_doi(paper.get("doi"))
    openalex_id = paper.get("openalex_id")
    with _connection() as connection:
        existing = None
        if doi:
            existing = connection.execute(
                "SELECT * FROM papers WHERE doi = ? ORDER BY created_at LIMIT 1", (doi,)
            ).fetchone()
        if existing is None and openalex_id:
            existing = connection.execute(
                "SELECT * FROM papers WHERE openalex_id = ? ORDER BY created_at LIMIT 1",
                (openalex_id,),
            ).fetchone()

        if existing:
            existing_id = existing["id"]
            metadata = {
                "openalex_id": openalex_id,
                "doi": doi,
                "title": paper.get("title"),
                "authors_json": json.dumps(paper.get("authors") or [], ensure_ascii=False),
                "publication_year": paper.get("year"),
                "publication_type": paper.get("publication_type"),
                "cited_by_count": paper.get("cited_by_count"),
                "abstract": paper.get("abstract"),
                "open_access": 1 if paper.get("open_access") is True else 0,
                "landing_page_url": paper.get("landing_page_url"),
                "pdf_url": paper.get("pdf_url"),
            }
            for field, value in metadata.items():
                if field == "open_access":
                    metadata[field] = int(bool(existing[field]) or bool(value))
                elif value in (None, "", "[]") and existing[field] not in (None, "", "[]"):
                    metadata[field] = existing[field]
            connection.execute(
                """UPDATE papers SET openalex_id=:openalex_id, doi=:doi, title=:title,
                   authors_json=:authors_json, publication_year=:publication_year,
                   publication_type=:publication_type, cited_by_count=:cited_by_count,
                   abstract=:abstract, open_access=:open_access,
                   landing_page_url=:landing_page_url, pdf_url=:pdf_url WHERE id=:id""",
                {**metadata, "id": existing_id},
            )
            row = connection.execute(
                "SELECT * FROM papers WHERE id = ?", (existing_id,)
            ).fetchone()
            return _decode_paper(row)

        paper_id = uuid.uuid4().hex
        title = paper.get("title") or "Untitled paper"
        connection.execute(
            """INSERT INTO papers (
                id, openalex_id, doi, title, authors_json, publication_year,
                publication_type, cited_by_count, abstract, open_access,
                landing_page_url, pdf_url, source_type, processing_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'openalex', 'metadata_only', ?)""",
            (
                paper_id,
                openalex_id,
                doi,
                title,
                json.dumps(paper.get("authors") or [], ensure_ascii=False),
                paper.get("year"),
                paper.get("publication_type"),
                paper.get("cited_by_count"),
                paper.get("abstract"),
                1 if paper.get("open_access") is True else 0,
                paper.get("landing_page_url"),
                paper.get("pdf_url"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        row = connection.execute(
            "SELECT * FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
    return _decode_paper(row)


def save_uploaded_pdf(
    original_filename: str,
    pdf_bytes: bytes,
    page_texts: Sequence[str],
    extraction_details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    init_db()
    paper_id = uuid.uuid4().hex
    upload_dir = data_dir() / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_path = upload_dir / f"{paper_id}.pdf"
    temporary_path = upload_dir / f".{paper_id}.part"
    temporary_path.write_bytes(pdf_bytes)
    temporary_path.replace(stored_path)

    details = dict(extraction_details or {})
    raw_metadata = details.get("metadata") or {}
    document_metadata = {
        str(key): str(value).strip()
        for key, value in raw_metadata.items()
        if str(value or "").strip()
    }
    extracted_title = document_metadata.get("title", "").strip()
    title = extracted_title if extracted_title and extracted_title.casefold() not in {
        "untitled", "untitled document", "microsoft word",
    } else Path(original_filename).stem or "Uploaded paper"
    author_value = document_metadata.get("author", "")
    authors = [value.strip() for value in author_value.split(";") if value.strip()]
    if author_value and not authors:
        authors = [author_value]

    page_chunks: list[tuple[int, int, str, str]] = []
    active_section = "unclassified"
    ordinals: dict[int, int] = {}
    for page_number, text in enumerate(page_texts, start=1):
        passages, active_section = split_page_sections(page_number, text, active_section)
        for passage in passages:
            for chunk in chunk_page_text(passage["text"]):
                ordinal = ordinals.get(page_number, 0)
                page_chunks.append((page_number, ordinal, passage["section"], chunk))
                ordinals[page_number] = ordinal + 1

    status = "processed" if page_chunks else "no_text"
    message_parts: list[str] = []
    empty_pages = [
        page_number for page_number, text in enumerate(page_texts, start=1)
        if not str(text or "").strip()
    ]
    ocr_pages = [int(number) for number in details.get("ocr_page_numbers", [])]
    failed_ocr_pages = [int(number) for number in details.get("ocr_failed_pages", [])]
    if not page_chunks:
        if details.get("ocr_available"):
            message_parts.append("No readable text was extracted, including from available OCR.")
        elif details.get("tesseract_available") and not details.get("ocr_enabled", True):
            message_parts.append(
                "No selectable text was found. OCR is disabled; set LITLENS_ENABLE_OCR=true to try OCR."
            )
        else:
            message_parts.append(
                "No selectable text was found. Tesseract is unavailable; install it and configure "
                "LITLENS_TESSERACT_PATH to try OCR."
            )
    elif empty_pages:
        message_parts.append(
            "Text was not extracted from page(s) " + ", ".join(map(str, empty_pages)) + "."
        )
    if ocr_pages:
        message_parts.append(
            "OCR extracted text from page(s) " + ", ".join(map(str, ocr_pages)) + "."
        )
    if failed_ocr_pages:
        message_parts.append(
            "OCR failed on page(s) " + ", ".join(map(str, failed_ocr_pages)) + "."
        )
    table_count = int(details.get("table_count", 0) or 0)
    if table_count:
        message_parts.append(
            f"Text from {table_count} detectable table(s) was included; figures and image meaning were not interpreted."
        )
    elif status == "processed":
        message_parts.append(
            "Figures and image meaning were not interpreted by text extraction."
        )
    message = " ".join(message_parts) or None

    try:
        with _connection() as connection:
            connection.execute(
                """INSERT INTO papers (
                    id, title, authors_json, document_metadata_json, source_type,
                    original_filename, stored_pdf_path, processing_status,
                    processing_message, page_count, created_at
                ) VALUES (?, ?, ?, ?, 'upload', ?, ?, ?, ?, ?, ?)""",
                (
                    paper_id,
                    title,
                    json.dumps(authors, ensure_ascii=False),
                    json.dumps(document_metadata, ensure_ascii=False),
                    original_filename,
                    str(stored_path),
                    status,
                    message,
                    len(page_texts),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            for page_number, text in enumerate(page_texts, start=1):
                connection.execute(
                    "INSERT INTO pages (paper_id, page_number, text) VALUES (?, ?, ?)",
                    (paper_id, page_number, text),
                )
            for page_number, ordinal, section, text in page_chunks:
                connection.execute(
                    "INSERT INTO chunks (id, paper_id, page_number, ordinal, section, text) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (uuid.uuid4().hex, paper_id, page_number, ordinal, section, text),
                )
    except Exception:
        stored_path.unlink(missing_ok=True)
        raise

    return {
        "paper_id": paper_id,
        "title": title,
        "original_filename": original_filename,
        "processing_status": status,
        "processing_message": message,
        "page_count": len(page_texts),
        "chunk_count": len(page_chunks),
        "table_count": table_count,
        "ocr_page_numbers": ocr_pages,
        "document_metadata": document_metadata,
    }


def get_pages(paper_id: str) -> list[dict[str, Any]]:
    init_db()
    with _connection() as connection:
        rows = connection.execute(
            "SELECT page_number, text FROM pages WHERE paper_id = ? ORDER BY page_number",
            (paper_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_chunks(paper_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    init_db()
    with _connection() as connection:
        if paper_ids is None:
            rows = connection.execute(
                """SELECT c.id AS chunk_id, c.paper_id, p.title, c.page_number,
                   c.ordinal, c.section, c.text FROM chunks c JOIN papers p ON p.id = c.paper_id
                   ORDER BY c.paper_id, c.page_number, c.ordinal"""
            ).fetchall()
        else:
            ids = list(dict.fromkeys(paper_ids))
            if not ids:
                return []
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(
                f"""SELECT c.id AS chunk_id, c.paper_id, p.title, c.page_number,
                    c.ordinal, c.section, c.text FROM chunks c JOIN papers p ON p.id = c.paper_id
                    WHERE c.paper_id IN ({placeholders})
                    ORDER BY c.paper_id, c.page_number, c.ordinal""",
                ids,
            ).fetchall()
    return [dict(row) for row in rows]


def delete_paper(paper_id: str) -> str | None:
    init_db()
    with _connection() as connection:
        row = connection.execute(
            "SELECT stored_pdf_path FROM papers WHERE id = ?", (paper_id,)
        ).fetchone()
        if row is None:
            return None
        stored_path = row["stored_pdf_path"]
        connection.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
    return stored_path or ""


def get_evidence_documents(
    paper_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return traceable PDF chunks and indexed abstracts for retrieval."""
    chunks = get_chunks(paper_ids)
    for chunk in chunks:
        chunk["source_kind"] = "pdf"

    papers = list_papers()
    selected = set(paper_ids) if paper_ids is not None else None
    abstracts = []
    for paper in papers:
        if selected is not None and paper["id"] not in selected:
            continue
        metadata = [f"Title: {paper['title']}"]
        if paper.get("authors"):
            metadata.append("Authors: " + ", ".join(paper["authors"]))
        if paper.get("publication_year"):
            metadata.append(f"Publication year: {paper['publication_year']}")
        if paper.get("doi"):
            metadata.append(f"DOI: {paper['doi']}")
        abstracts.append({
            "chunk_id": f"metadata:{paper['id']}",
            "paper_id": paper["id"],
            "title": paper["title"],
            "page_number": None,
            "ordinal": -2,
            "section": "bibliographic metadata",
            "text": "\n".join(metadata),
            "source_kind": "metadata",
        })
        abstract = paper.get("abstract")
        if isinstance(abstract, str) and abstract.strip():
            abstracts.append({
                "chunk_id": f"abstract:{paper['id']}",
                "paper_id": paper["id"],
                "title": paper["title"],
                "page_number": None,
                "ordinal": -1,
                "section": "abstract",
                "text": abstract,
                "source_kind": "abstract",
            })
    return chunks + abstracts
