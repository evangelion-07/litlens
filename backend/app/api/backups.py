from pathlib import Path
import tempfile

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from app.services.backup_service import MAX_ARCHIVE_BYTES, export_library, restore_library
from app.services.library_repository import data_dir

router = APIRouter(prefix="/backups", tags=["Research backups"])


@router.get("/export")
def export_backup():
    try:
        path = export_library()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return FileResponse(path, filename="LitLens-research-backup.zip", media_type="application/zip", background=BackgroundTask(path.unlink, missing_ok=True))


@router.post("/restore")
async def restore_backup(request: Request):
    folder = data_dir() / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(suffix=".zip", dir=folder, delete=False)
    path = Path(handle.name)
    try:
        size = 0
        with handle:
            async for block in request.stream():
                size += len(block)
                if size > MAX_ARCHIVE_BYTES:
                    raise HTTPException(413, "Backup must be smaller than 512 MB.")
                handle.write(block)
        try:
            return await run_in_threadpool(restore_library, path)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    finally:
        handle.close()
        path.unlink(missing_ok=True)
