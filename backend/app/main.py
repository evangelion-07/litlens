import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.analysis import router as analysis_router
from app.api.assistant import router as assistant_router
from app.api.library import router as library_router
from app.api.papers import router as papers_router
from app.services.analysis_repository import fail_interrupted_analyses
from app.api.auth import router as auth_router
from app.api.settings import router as settings_router
from app.api.backups import router as backups_router
from app.security import AccountBoundary
from app.services.user_context import profile_directory, storage_root

app = FastAPI(
    title="LitLens API",
    description="Research Paper Intelligence Agent",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

origins = [
    origin.strip()
    for origin in os.getenv("LITLENS_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-LitLens-Desktop"],
)
app.add_middleware(AccountBoundary)


@app.get("/")
def home():
    frontend = os.getenv("LITLENS_FRONTEND_DIR")
    if frontend and (Path(frontend) / "index.html").is_file():
        return FileResponse(Path(frontend) / "index.html")
    return {
        "project": "LitLens",
        "message": "Research Paper Intelligence Agent API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.on_event("startup")
def recover_interrupted_analysis_jobs():
    fail_interrupted_analyses()
    root = storage_root() / "profiles"
    if root.exists():
        for folder in root.iterdir():
            if folder.is_dir() and (folder / "litlens.sqlite3").exists():
                token = profile_directory.set(folder)
                try:
                    fail_interrupted_analyses()
                finally:
                    profile_directory.reset(token)


app.include_router(analysis_router)
app.include_router(papers_router)
app.include_router(library_router)
app.include_router(assistant_router)
app.include_router(auth_router)
app.include_router(settings_router)
app.include_router(backups_router)
frontend = os.getenv("LITLENS_FRONTEND_DIR")
if frontend and (Path(frontend) / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=Path(frontend) / "assets"), name="assets")



