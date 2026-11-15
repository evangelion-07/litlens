"""Entry point for the bundled, loopback-only desktop backend."""
import os
import sys
import uvicorn


if __name__ == "__main__":
    # PyInstaller's windowed builds may not provide standard streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["LITLENS_PORT"]),
                access_log=False, log_level="warning")
