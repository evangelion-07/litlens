import hmac
import os

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse

from app.services.accounts import authenticate
from app.services.user_context import profile_directory, profile_user, storage_root


class AccountBoundary:
    """Pure ASGI boundary keeps the profile context until background work finishes."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope["path"]
        headers = dict(scope["headers"])
        secret = os.getenv("LITLENS_DESKTOP_SECRET", "")
        if path.startswith("/assets/") or path in {"/", "/health", "/favicon.ico"} or scope["method"] == "OPTIONS":
            return await self.app(scope, receive, send)
        if secret and not hmac.compare_digest(headers.get(b"x-litlens-desktop", b"").decode(), secret):
            return await JSONResponse({"detail": "Open this service from LitLens Desktop."}, 403)(scope, receive, send)
        if path in {"/auth/register", "/auth/login"}:
            return await self.app(scope, receive, send)
        token = headers.get(b"authorization", b"").decode().removeprefix("Bearer ")
        user = await run_in_threadpool(authenticate, token)
        if not user:
            return await JSONResponse({"detail": "Sign in to access your research library."}, 401)(scope, receive, send)
        context = profile_directory.set(storage_root() / "profiles" / user["id"])
        identity = profile_user.set(user)
        try:
            await self.app(scope, receive, send)
        finally:
            profile_directory.reset(context)
            profile_user.reset(identity)
