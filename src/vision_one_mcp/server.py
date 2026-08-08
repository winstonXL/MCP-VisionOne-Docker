"""Entry point: a read-only FastMCP server for Trend Vision One, served over Streamable HTTP.

Run directly for local development:

    python -m vision_one_mcp.server

Or via the Dockerfile / docker-compose.yml in this repo for a real deployment.
"""

from __future__ import annotations

import logging
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route

from vision_one_mcp.auth_middleware import BearerAuthMiddleware
from vision_one_mcp.client import VisionOneApiError, VisionOneClient
from vision_one_mcp.config import load_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vision_one_mcp")

settings = load_settings()
client = VisionOneClient(settings.vision_one_api_key, settings.vision_one_base_url)

mcp = FastMCP("vision-one-mcp-python", json_response=True)


@mcp.tool()
async def workbench_alerts_list(
    start: str | None = None,
    end: str | None = None,
    investigation_status: str | None = None,
    top: int = 50,
) -> list[dict[str, Any]]:
    """List Trend Vision One Workbench alerts.

    Args:
        start: ISO 8601 start of the time range (e.g. "2026-08-01T00:00:00Z"). Omit for no lower bound.
        end: ISO 8601 end of the time range. Omit to default to "now".
        investigation_status: Filter to a single status, e.g. "New", "In Progress", "Resolved".
        top: Maximum number of alerts to return (across pagination). Default 50.
    """
    try:
        return await client.list_workbench_alerts(
            start=start, end=end, investigation_status=investigation_status, top=top
        )
    except VisionOneApiError as exc:
        logger.warning("workbench_alerts_list failed: %s", exc)
        raise


@mcp.tool()
async def workbench_alert_detail_get(alert_id: str) -> dict[str, Any]:
    """Get full details for a single Trend Vision One Workbench alert.

    Args:
        alert_id: The Workbench alert ID (as returned by workbench_alerts_list).
    """
    try:
        return await client.get_workbench_alert(alert_id)
    except VisionOneApiError as exc:
        logger.warning("workbench_alert_detail_get failed: %s", exc)
        raise


@mcp.tool()
async def threatintel_suspicious_objects_list(top: int = 50) -> list[dict[str, Any]]:
    """List entries in the Trend Vision One Suspicious Object List (domains, IPs, file
    hashes, URLs, and email addresses your organization has flagged as suspicious).

    Args:
        top: Maximum number of entries to return (across pagination). Default 50.
    """
    try:
        return await client.list_suspicious_objects(top=top)
    except VisionOneApiError as exc:
        logger.warning("threatintel_suspicious_objects_list failed: %s", exc)
        raise


@mcp.tool()
async def threatintel_suspicious_object_exceptions_list(top: int = 50) -> list[dict[str, Any]]:
    """List entries in the Trend Vision One Threat Intelligence Exception List (objects
    explicitly excluded from suspicious-object matching/blocking).

    Args:
        top: Maximum number of entries to return (across pagination). Default 50.
    """
    try:
        return await client.list_suspicious_object_exceptions(top=top)
    except VisionOneApiError as exc:
        logger.warning("threatintel_suspicious_object_exceptions_list failed: %s", exc)
        raise


async def _healthz(_request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_app():
    """Build the ASGI app: FastMCP's Streamable HTTP app, plus /healthz and bearer auth."""
    app = mcp.streamable_http_app()
    app.router.routes.insert(0, Route("/healthz", _healthz))
    app.add_middleware(BearerAuthMiddleware, expected_token=settings.mcp_bearer_token)
    return app


app = build_app()


def main() -> None:
    logger.info(
        "Starting vision-one-mcp-python on %s:%s (Vision One base URL: %s)",
        settings.host,
        settings.port,
        settings.vision_one_base_url,
    )
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
