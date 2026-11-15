"""Portable research archives. Credentials and machine-bound secrets never leave a profile."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path

from app.schemas.analysis import AnalysisReport
from app.services.library_repository import _connection, data_dir, init_db

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024 * 1024
TABLES = ("papers", "pages", "chunks", "paper_analyses", "chat_turns")


def _idle(connection):
    if connection.execute("SELECT 1 FROM paper_analyses WHERE status IN ('queued','running') LIMIT 1").fetchone():
        raise ValueError("Wait for the current analysis to finish before backing up or restoring.")


def export_library() -> Path:
    init_db()
    folder = data_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(suffix=".zip", dir=folder, delete=False)
    target = Path(handle.name)
    handle.close()
    try:
        with _connection() as connection, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            connection.execute("BEGIN IMMEDIATE")
            _idle(connection)
            tables = {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")] for table in TABLES}
            files = {}
            total = 0
            for paper in tables["papers"]:
                original = paper.pop("stored_pdf_path", None)
                if not original:
                    continue
                pdf = Path(original).resolve()
                if not pdf.is_relative_to((data_dir() / "uploads").resolve()) or not pdf.is_file():
                    raise ValueError("A stored PDF is missing. Restore the file or remove its paper before exporting.")
                content = pdf.read_bytes()
                total += len(content)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("This library exceeds the 512 MB portable backup limit.")
                name = f"pdfs/{uuid.uuid4().hex}.pdf"
                files[paper["id"]] = {"name": name, "sha256": hashlib.sha256(content).hexdigest()}
                archive.writestr(name, content)
            manifest = json.dumps({"format": "litlens-research", "version": 1, "tables": tables, "files": files}, ensure_ascii=False).encode("utf-8")
            if len(manifest) > MAX_MANIFEST_BYTES or total + len(manifest) > MAX_ARCHIVE_BYTES:
                raise ValueError("This library exceeds the portable backup limit.")
            archive.writestr("manifest.json", manifest)
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def _remap(value, mapping):
    if isinstance(value, dict):
        return {key: mapping.get(item, item) if key in {"paper_id", "analysis_id", "chunk_id"} and isinstance(item, str) else _remap(item, mapping) for key, item in value.items()}
    if isinstance(value, list):
        return [_remap(item, mapping) for item in value]
    return value


def restore_library(source: Path) -> dict:
    """Validate the complete archive, then add papers with new IDs in one transaction."""
    created: list[Path] = []
    try:
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > 10001 or len(names) != len(set(names)) or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError("Backup is too large or contains duplicate entries.")
            if archive.getinfo("manifest.json").file_size > MAX_MANIFEST_BYTES:
                raise ValueError("Backup manifest is too large.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest.get("format") != "litlens-research" or manifest.get("version") != 1:
                raise ValueError("Unsupported LitLens backup version.")
            tables, files = manifest["tables"], manifest["files"]
            if not isinstance(tables, dict) or set(tables) != set(TABLES) or not isinstance(files, dict):
                raise ValueError("Invalid backup tables.")
            if any(not isinstance(rows, list) or len(rows) > 250000 for rows in tables.values()):
                raise ValueError("Invalid backup records.")
            paper_ids = {p["id"] for p in tables["papers"]}
            if len(paper_ids) != len(tables["papers"]) or not set(files).issubset(paper_ids):
                raise ValueError("Invalid paper references.")
            pdfs = {}
            expected = {"manifest.json"}
            for paper_id, record in files.items():
                name = record["name"]
                # Never extract paths supplied by an archive.
                if not isinstance(name, str) or not name.startswith("pdfs/") or ".." in name or "\\" in name:
                    raise ValueError("Invalid PDF entry.")
                entry = archive.getinfo(name)
                if entry.file_size > 20 * 1024 * 1024:
                    raise ValueError("A PDF exceeds the 20 MB import limit.")
                content = archive.read(name)
                if not content.startswith(b"%PDF-") or hashlib.sha256(content).hexdigest() != record["sha256"]:
                    raise ValueError("A PDF is damaged or its checksum does not match.")
                pdfs[paper_id] = content
                expected.add(name)
            if set(names) != expected:
                raise ValueError("Unexpected files in backup.")

        init_db()
        with _connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            _idle(connection)
            mapping = {}
            for table in ("papers", "chunks", "paper_analyses"):
                for row in tables[table]:
                    old = row["id"]
                    if not isinstance(old, str) or not old or old in mapping:
                        raise ValueError("Duplicate or invalid record identifier.")
                    mapping[old] = uuid.uuid4().hex
            mapping.update({f"abstract:{old}": f"abstract:{mapping[old]}" for old in paper_ids})
            for table in TABLES:
                columns = {r["name"] for r in connection.execute(f"PRAGMA table_info({table})")}
                for record in tables[table]:
                    row = dict(record)
                    permitted = columns - ({"stored_pdf_path"} if table == "papers" else set())
                    if set(row) != permitted or any(not isinstance(v, (str, int, float, type(None))) for v in row.values()):
                        raise ValueError("Invalid backup record fields.")
                    if table != "papers" and row["paper_id"] not in paper_ids:
                        raise ValueError("A record belongs to a missing paper.")
                    if table == "papers":
                        old = row["id"]
                        row["stored_pdf_path"] = None
                        if old in pdfs:
                            destination = data_dir() / "uploads" / f"{mapping[old]}.pdf"
                            destination.parent.mkdir(parents=True, exist_ok=True)
                            created.append(destination)
                            with destination.open("xb") as output:
                                output.write(pdfs[old])
                            row["stored_pdf_path"] = str(destination.resolve())
                        elif row["source_type"] == "upload":
                            raise ValueError("An uploaded paper is missing its PDF.")
                        if not isinstance(json.loads(row["authors_json"]), list) or not isinstance(json.loads(row["document_metadata_json"]), dict):
                            raise ValueError("Invalid paper metadata.")
                    elif table == "paper_analyses":
                        if row["status"] not in {"completed", "failed"}:
                            raise ValueError("Backup contains an unfinished analysis.")
                        if row["report_json"]:
                            report = AnalysisReport.model_validate_json(row["report_json"]).model_dump()
                            row["report_json"] = json.dumps(_remap(report, mapping))
                    elif table == "chat_turns":
                        row.pop("id")
                        if row["role"] not in {"user", "assistant"}:
                            raise ValueError("Invalid chat role.")
                        details = json.loads(row["details"])
                        if not isinstance(details, dict):
                            raise ValueError("Invalid chat details.")
                        row["details"] = json.dumps(_remap(details, mapping))
                    row = {key: mapping.get(value, value) if key in {"id", "paper_id"} else value for key, value in row.items()}
                    fields = list(row)
                    connection.execute(f"INSERT INTO {table} ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", list(row.values()))
        return {"papers_restored": len(paper_ids), "reports_restored": len(tables["paper_analyses"]), "chat_turns_restored": len(tables["chat_turns"])}
    except BaseException as exc:
        for path in created:
            path.unlink(missing_ok=True)
        if isinstance(exc, (ValueError, KeyError, TypeError, zipfile.BadZipFile, sqlite3.IntegrityError, RecursionError)):
            raise ValueError(f"Cannot restore this backup: {str(exc)[:200]}") from exc
        raise
