
from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Paths that must stay reachable without a token, e.g. the Docker HEALTHCHECK probe.
UNAUTHENTICATED_PATHS = {"/healthz"}


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, expected_token: str) -> None:
        self.app = app
        self._expected_header = f"Bearer {expected_token}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in UNAUTHENTICATED_PATHS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("latin-1")

        if auth_header != self._expected_header:
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
