from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.services.library_repository import _connection, init_db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    raw_report = result.pop("report_json", None)
    result["report"] = json.loads(raw_report) if raw_report else None
    return result


def create_analysis_record(analysis_id: str, paper_id: str) -> dict[str, Any]:
    init_db()
    timestamp = _now()
    with _connection() as connection:
        connection.execute(
            """INSERT INTO paper_analyses (
                id, paper_id, status, stage, progress, created_at, updated_at
            ) VALUES (?, ?, 'queued', 'queued', 0, ?, ?)""",
            (analysis_id, paper_id, timestamp, timestamp),
        )
    record = get_analysis_record(analysis_id)
    if record is None:
        raise RuntimeError("Analysis record was not persisted.")
    return record


def update_analysis_record(
    analysis_id: str,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    report: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any] | None:
    init_db()
    assignments = ["updated_at = ?"]
    values: list[Any] = [_now()]
    if status is not None:
        assignments.append("status = ?")
        values.append(status)
    if stage is not None:
        assignments.append("stage = ?")
        values.append(stage)
    if progress is not None:
        assignments.append("progress = ?")
        values.append(max(0, min(100, int(progress))))
    if report is not None:
        assignments.append("report_json = ?")
        values.append(json.dumps(report, ensure_ascii=False))
    if error is not None:
        assignments.append("error = ?")
        values.append(error)
    values.append(analysis_id)
    with _connection() as connection:
        connection.execute(
            f"UPDATE paper_analyses SET {', '.join(assignments)} WHERE id = ?",
            values,
        )
    return get_analysis_record(analysis_id)


def get_analysis_record(analysis_id: str) -> dict[str, Any] | None:
    init_db()
    with _connection() as connection:
        row = connection.execute(
            """SELECT a.id, a.paper_id, p.title AS paper_title, a.status, a.stage,
                      a.progress, a.report_json, a.error, a.created_at, a.updated_at
               FROM paper_analyses a JOIN papers p ON p.id = a.paper_id
               WHERE a.id = ?""",
            (analysis_id,),
        ).fetchone()
    return _decode(row)


def get_latest_analysis(paper_id: str) -> dict[str, Any] | None:
    init_db()
    with _connection() as connection:
        row = connection.execute(
            """SELECT a.id, a.paper_id, p.title AS paper_title, a.status, a.stage,
                      a.progress, a.report_json, a.error, a.created_at, a.updated_at
               FROM paper_analyses a JOIN papers p ON p.id = a.paper_id
               WHERE a.paper_id = ?
               ORDER BY a.created_at DESC LIMIT 1""",
            (paper_id,),
        ).fetchone()
    return _decode(row)


def list_analysis_records(limit: int = 50) -> list[dict[str, Any]]:
    init_db()
    bounded_limit = max(1, min(200, int(limit)))
    with _connection() as connection:
        rows = connection.execute(
            """SELECT a.id, a.paper_id, p.title AS paper_title, a.status, a.stage,
                      a.progress, a.report_json, a.error, a.created_at, a.updated_at
               FROM paper_analyses a JOIN papers p ON p.id = a.paper_id
               ORDER BY a.created_at DESC LIMIT ?""",
            (bounded_limit,),
        ).fetchall()
    return [_decode(row) for row in rows]


def fail_interrupted_analyses() -> int:
    """Mark jobs left in progress by a previous server process as interrupted."""
    init_db()
    timestamp = _now()
    with _connection() as connection:
        cursor = connection.execute(
            """UPDATE paper_analyses
               SET status = 'failed', stage = 'interrupted', progress = 100,
                   error = 'The server stopped before this analysis completed. Start a new analysis.',
                   updated_at = ?
               WHERE status IN ('queued', 'running')""",
            (timestamp,),
        )
    return cursor.rowcount