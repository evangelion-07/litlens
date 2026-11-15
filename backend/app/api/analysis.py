from __future__ import annotations

import logging
import os
import uuid
import asyncio
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response
from starlette.concurrency import run_in_threadpool

from app.schemas.analysis import (
    AnalysisCapabilities, AnalysisJob, AnalysisReport, AnalysisRequest,
)
from app.services.analysis_repository import (
    create_analysis_record, get_analysis_record, get_latest_analysis,
    list_analysis_records, update_analysis_record,
)
from app.services.analysis_service import analyze_paper
from app.services.library_repository import get_chunks, get_paper, get_pages
from app.services.llm_provider import configured_llm_provider
from app.services.pdf_service import _ocr_enabled, _pymupdf_module, _tesseract_available
from app.services.report_export import report_markdown, report_pdf, safe_report_filename
from app.services.review_retrieval import review_retrieval

router = APIRouter(prefix="/analysis", tags=["Paper analysis"])
logger = logging.getLogger(__name__)


def _job(record: dict[str, Any], include_report: bool = True) -> AnalysisJob:
    report = record.get("report") if include_report else None
    return AnalysisJob(
        analysis_id=record["id"],
        paper_id=record["paper_id"],
        paper_title=record["paper_title"],
        status=record["status"],
        stage=record["stage"],
        progress=record["progress"],
        error=record.get("error"),
        report=AnalysisReport.model_validate(report) if report else None,
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


def _ocr_available() -> bool:
    try:
        return _ocr_enabled() and _tesseract_available(_pymupdf_module())
    except Exception:
        return False


async def _execute_analysis_job(analysis_id: str, paper_id: str, use_external_ai: bool) -> None:
    update_analysis_record(analysis_id, status="running", stage="loading paper", progress=5)
    paper = await run_in_threadpool(get_paper, paper_id)
    if paper is None:
        update_analysis_record(
            analysis_id, status="failed", stage="failed", progress=100,
            error="The selected paper is no longer in the library.",
        )
        return
    pages = await run_in_threadpool(get_pages, paper_id)
    chunks = await run_in_threadpool(get_chunks, [paper_id])

    async def report_progress(progress: int, stage: str) -> None:
        update_analysis_record(
            analysis_id, status="running", stage=stage, progress=progress
        )

    try:
        await report_progress(8, "Indexing local embeddings and keyword evidence")
        retrieval = await review_retrieval(paper, pages, chunks)
        report = await analyze_paper(
            analysis_id, paper, pages, chunks,
            use_external_ai=use_external_ai,
            llm_provider=configured_llm_provider() if use_external_ai else None,
            progress=report_progress,
            review_context=retrieval.get("focus", {}),
        )
    except Exception as exc:
        if use_external_ai:
            logger.warning(
                "LitLens provider analysis failed for job %s (%s); creating local report.",
                analysis_id, type(exc).__name__,
            )
            report = await analyze_paper(
                analysis_id, paper, pages, chunks,
                use_external_ai=False,
                progress=report_progress,
                extra_caveats=(
                    "The configured AI provider was unavailable or returned an invalid report. "
                    "A local extractive report was generated instead; no external critique is included.",
                ),
            )
        else:
            logger.exception("LitLens local analysis failed for job %s.", analysis_id)
            update_analysis_record(
                analysis_id, status="failed", stage="failed", progress=100,
                error="Paper analysis failed. Check the extraction status and try again.",
            )
            return
    report.retrieval = retrieval
    if retrieval.get("notice"):
        report.caveats.append(retrieval["notice"])
    update_analysis_record(
        analysis_id,
        status="completed",
        stage="complete",
        progress=100,
        report=report.model_dump(),
        error=None,
    )


def _run_analysis_job(analysis_id: str, paper_id: str, use_external_ai: bool) -> None:
    # Starlette runs sync background tasks in its thread pool. This prevents local
    # extraction/report work from freezing status, sign-in, and other API requests.
    try:
        asyncio.run(_execute_analysis_job(analysis_id, paper_id, use_external_ai))
    except Exception:
        logger.exception("Analysis job failed: %s", analysis_id)
        update_analysis_record(analysis_id, status="failed", stage="failed", progress=100,
                               error="Analysis could not finish. Your paper is saved; retry from its report tab.")


@router.get("/capabilities", response_model=AnalysisCapabilities)
def analysis_capabilities():
    provider = configured_llm_provider()
    try:
        max_upload = max(1, int(os.getenv("LITLENS_MAX_UPLOAD_MB", "20")))
    except ValueError:
        max_upload = 20
    return AnalysisCapabilities(
        llm_configured=provider is not None,
        llm_model=os.getenv("LLM_MODEL") if provider is not None else None,
        ocr_available=_ocr_available(),
        crossref_available=True,
        max_upload_mb=max_upload,
    )


@router.get("/history", response_model=list[AnalysisJob])
def analysis_history(limit: int = Query(default=50, ge=1, le=200)):
    return [_job(item, include_report=False) for item in list_analysis_records(limit)]


@router.post("/papers/{paper_id}", response_model=AnalysisJob, status_code=202)
def start_paper_analysis(
    paper_id: str,
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
):
    paper = get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    existing = get_latest_analysis(paper_id)
    if existing and existing["status"] in {"queued", "running"}:
        return _job(existing)
    if request.use_external_ai and configured_llm_provider() is None:
        raise HTTPException(
            status_code=422,
            detail="No AI model is configured. Select Ollama or an API provider in Settings.",
        )
    analysis_id = uuid.uuid4().hex
    record = create_analysis_record(analysis_id, paper_id)
    background_tasks.add_task(
        _run_analysis_job, analysis_id, paper_id, request.use_external_ai
    )
    return _job(record)


@router.get("/papers/{paper_id}/latest", response_model=AnalysisJob)
def latest_paper_analysis(paper_id: str):
    if get_paper(paper_id) is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    record = get_latest_analysis(paper_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No analysis history exists for this paper.")
    return _job(record)


@router.get("/{analysis_id}/export")
def export_analysis(
    analysis_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|pdf)$"),
):
    record = get_analysis_record(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis was not found.")
    if record["status"] != "completed" or not record.get("report"):
        raise HTTPException(status_code=409, detail="Wait for the analysis to complete before exporting.")
    report = record["report"]
    filename = safe_report_filename(record["paper_title"])
    if format == "markdown":
        body = report_markdown(report)
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}-analysis.md"'},
        )
    try:
        body = report_pdf(report)
    except Exception as exc:
        logger.exception("Could not render PDF export for analysis %s.", analysis_id)
        raise HTTPException(status_code=503, detail="PDF export is temporarily unavailable.") from exc
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}-analysis.pdf"'},
    )


@router.get("/{analysis_id}", response_model=AnalysisJob)
def get_analysis(analysis_id: str):
    record = get_analysis_record(analysis_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis was not found.")
    return _job(record)
