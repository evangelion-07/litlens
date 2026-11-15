"""Request-local storage boundaries, also propagated to worker threads."""
from contextvars import ContextVar
from pathlib import Path

profile_directory: ContextVar[Path | None] = ContextVar("profile_directory", default=None)
profile_user: ContextVar[dict | None] = ContextVar("profile_user", default=None)


def storage_root() -> Path:
    import os
    root = Path(__file__).resolve().parents[3]
    configured = Path(os.getenv("LITLENS_DATA_DIR", str(root / "data"))).expanduser()
    return configured if configured.is_absolute() else (root / configured).resolve()
