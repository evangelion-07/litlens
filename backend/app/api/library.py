from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.schemas.paper import PaperMetadata
from app.schemas.comparison import CompareRequest
from app.services.library_repository import (
    data_dir,
    delete_paper,
    get_paper,
    get_pages,
    list_papers,
    save_openalex_paper,
    save_uploaded_pdf,
)
from app.services.comparison_service import compare_papers
from app.services.pdf_service import (
    InvalidPdfError,
    PdfDependencyMissing,
    extract_pdf_document,
)

router = APIRouter(prefix="/library", tags=["Research library"])


def _upload_limit_bytes() -> int:
    try:
        return max(1, int(os.getenv("LITLENS_MAX_UPLOAD_MB", "20"))) * 1024 * 1024
    except ValueError:
        return 20 * 1024 * 1024


def _safe_filename(filename: str) -> str:
    name = filename.replace("\\", "/").split("/")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:180] or "uploaded-paper.pdf"


@router.get("/papers")
def list_library_papers():
    papers = list_papers()
    return {"count": len(papers), "results": papers}


@router.post("/papers")
def save_search_result(paper: PaperMetadata):
    saved = save_openalex_paper(paper.model_dump())
    return {"paper": saved, "created": saved["source_type"] == "openalex"}


@router.post("/upload")
async def upload_pdf(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Query(min_length=1, max_length=255),
):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Upload a PDF file using application/pdf.")

    maximum_size = _upload_limit_bytes()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > maximum_size:
            raise HTTPException(
                status_code=413,
                detail=f"PDF exceeds the {maximum_size // (1024 * 1024)} MB upload limit.",
            )

    pdf_bytes = bytes(body)
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if b"%PDF-" not in pdf_bytes[:1024]:
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    original_filename = _safe_filename(filename)
    if Path(original_filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="The uploaded filename must end in .pdf.")

    try:
        extraction = await run_in_threadpool(extract_pdf_document, pdf_bytes)
        saved = await run_in_threadpool(
            save_uploaded_pdf, original_filename, pdf_bytes,
            extraction["page_texts"], extraction,
        )
    except PdfDependencyMissing as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvalidPdfError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not store the uploaded PDF.") from exc

    from app.services.user_context import profile_directory
    if profile_directory.get() is not None:
        from app.services.settings import get_settings
        from app.services.analysis_repository import create_analysis_record
        from app.api.analysis import _run_analysis_job, _job
        preferences = get_settings()
        if preferences["auto_analyze"]:
            analysis_id = uuid4().hex
            record = await run_in_threadpool(create_analysis_record, analysis_id, saved["paper_id"])
            background_tasks.add_task(_run_analysis_job, analysis_id, saved["paper_id"], preferences["provider"] != "local")
            saved["analysis"] = _job(record).model_dump()
    return saved


@router.get("/papers/{paper_id}")
def get_library_paper(paper_id: str):
    paper = get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    return {"paper": paper}


@router.get("/papers/{paper_id}/pages")
def get_library_paper_pages(paper_id: str):
    if get_paper(paper_id) is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    return {"paper_id": paper_id, "pages": get_pages(paper_id)}


@router.get("/papers/{paper_id}/pdf")
def get_library_paper_pdf(paper_id: str):
    paper = get_paper(paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    stored_path = paper.get("stored_pdf_path")
    if not stored_path:
        raise HTTPException(status_code=404, detail="This library record has no uploaded PDF.")
    path = Path(stored_path).resolve()
    upload_root = (data_dir() / "uploads").resolve()
    if not path.is_relative_to(upload_root) or not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=404, detail="The stored PDF is unavailable.")
    return FileResponse(path, media_type="application/pdf", filename=path.name, content_disposition_type="inline")


@router.delete("/papers/{paper_id}")
def remove_library_paper(paper_id: str):
    stored_path = delete_paper(paper_id)
    if stored_path is None:
        raise HTTPException(status_code=404, detail="Paper was not found in the library.")
    try:
        if stored_path:
            Path(stored_path).unlink(missing_ok=True)
    except OSError:
        # The database record is already gone; report the cleanup issue for visibility.
        raise HTTPException(status_code=500, detail="Paper metadata was removed, but its PDF file could not be deleted.")
    return {"deleted": True, "paper_id": paper_id}



@router.post("/compare")
def compare_library_papers(request: CompareRequest):
    records = []
    missing = []
    for paper_id in request.paper_ids:
        paper = get_paper(paper_id)
        if paper is None:
            missing.append(paper_id)
        else:
            records.append({"paper": paper, "pages": get_pages(paper_id)})
    if missing:
        raise HTTPException(
            status_code=404,
            detail={"message": "Some selected papers were not found in the library.", "missing_paper_ids": missing},
        )
    return compare_papers(records)

