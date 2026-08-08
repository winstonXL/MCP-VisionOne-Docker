"""Static bearer-token auth for the MCP Streamable HTTP app.

Deliberately *not* using mcp.server.auth's OAuth 2.1 TokenVerifier flow — that's built
around discovering and trusting a separate Authorization Server (RFC 9728), which is
overkill for a single-tenant personal/customer deployment where the server itself issues
one static shared secret out of band (via a Kubernetes Secret).

This is plain ASGI middleware (not Starlette's BaseHTTPMiddleware) specifically so it
never buffers the response body — Streamable HTTP keeps long-lived, chunked connections
open, and BaseHTTPMiddleware has a history of interacting badly with streaming responses.
"""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Paths that must stay reachable without a token, e.g. Kubernetes liveness/readiness probes.
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
