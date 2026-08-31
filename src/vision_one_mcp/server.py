"""Entry point: a read-only FastMCP server for Trend Vision One, served over Streamable HTTP.
   Run via the Dockerfile / docker-compose.yml in this repo for a full deployment.
"""

from __future__ import annotations

import logging
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

from vision_one_mcp.auth_middleware import BearerAuthMiddleware
from vision_one_mcp.client import VisionOneApiError, VisionOneClient
from vision_one_mcp.config import load_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vision_one_mcp")

settings = load_settings()
client = VisionOneClient(settings.vision_one_api_key, settings.vision_one_base_url)

mcp = FastMCP(
    "vision-one-mcp-python",
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)


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


@mcp.tool()
async def endpoint_security_endpoints_list(
    order_by: str | None = None,
    select: str | None = None,
    filter_query: str | None = None,
    top: int = 50,
) -> list[dict[str, Any]]:
    """List endpoints (managed devices) known to Trend Vision One Endpoint Security.

    Args:
        order_by: Vision One orderBy expression, e.g. "lastActionDateTime desc".
        select: Comma-separated list of fields to include in the response, to trim payload size.
        filter_query: A raw TMV1-Filter expression, e.g. "endpointName eq 'DESKTOP-1'". Omit for no filter.
        top: Maximum number of endpoints to return (across pagination). Default 50.
    """
    try:
        return await client.list_endpoints(
            order_by=order_by, select=select, filter_query=filter_query, top=top
        )
    except VisionOneApiError as exc:
        logger.warning("endpoint_security_endpoints_list failed: %s", exc)
        raise


@mcp.tool()
async def crem_vulnerable_devices_list(
    order_by: str | None = None,
    cve_detection_status: str | None = None,
    filter_query: str | None = None,
    top: int = 50,
) -> list[dict[str, Any]]:
    """List devices with detected vulnerabilities (CVEs), per Trend Vision One Attack Surface
    Risk Management / Cyber Risk Exposure Management.

    Args:
        order_by: Vision One orderBy expression, e.g. "riskScore desc".
        cve_detection_status: Filter by CVE detection status (exact accepted values depend on
            your Vision One tenant -- check there if a value is rejected).
        filter_query: A raw TMV1-Filter expression for additional filtering.
        top: Maximum number of devices to return (across pagination). Default 50.
    """
    try:
        return await client.list_vulnerable_devices(
            order_by=order_by,
            cve_detection_status=cve_detection_status,
            filter_query=filter_query,
            top=top,
        )
    except VisionOneApiError as exc:
        logger.warning("crem_vulnerable_devices_list failed: %s", exc)
        raise


@mcp.tool()
async def crem_high_risk_users_list(
    order_by: str | None = None,
    filter_query: str | None = None,
    top: int = 50,
) -> list[dict[str, Any]]:
    """List users with elevated Vision One risk scores, per Attack Surface Risk Management /
    Cyber Risk Exposure Management. Each entry includes the user's overall riskScore plus the
    individual riskyEvents (e.g. leaked credentials, account compromise indicators) that
    contributed to it.

    Args:
        order_by: Vision One orderBy expression, e.g. "riskScore desc".
        filter_query: A raw TMV1-Filter expression for additional filtering.
        top: Maximum number of users to return (across pagination). Default 50.
    """
    try:
        return await client.list_high_risk_users(
            order_by=order_by, filter_query=filter_query, top=top
        )
    except VisionOneApiError as exc:
        logger.warning("crem_high_risk_users_list failed: %s", exc)
        raise


@mcp.tool()
async def crem_discovered_domain_accounts_list(
    order_by: str | None = None,
    filter_query: str | None = None,
    top: int = 50,
) -> list[dict[str, Any]]:
    """List domain accounts discovered by Trend Vision One Attack Surface Risk Management
    (accounts found across your environment via asset discovery, independent of whether
    they're actively managed).

    Args:
        order_by: Vision One orderBy expression, e.g. "riskLevel desc".
        filter_query: A raw TMV1-Filter expression for additional filtering.
        top: Maximum number of accounts to return (across pagination). Default 50.
    """
    try:
        return await client.list_attack_surface_domain_accounts(
            order_by=order_by, filter_query=filter_query, top=top
        )
    except VisionOneApiError as exc:
        logger.warning("crem_discovered_domain_accounts_list failed: %s", exc)
        raise


@mcp.tool()
async def crem_discovered_devices_list(
    order_by: str | None = None,
    filter_query: str | None = None,
    top: int = 50,
    last_detected_start: str | None = None,
    last_detected_end: str | None = None,
    first_seen_start: str | None = None,
    first_seen_end: str | None = None,
) -> list[dict[str, Any]]:
    """List devices discovered by Trend Vision One Attack Surface Risk Management (asset
    discovery -- devices seen in your environment, independent of whether they're actively
    managed by an endpoint agent).

    Args:
        order_by: Vision One orderBy expression, e.g. "riskLevel desc".
        filter_query: A raw TMV1-Filter expression for additional filtering.
        top: Maximum number of devices to return (across pagination). Default 50.
        last_detected_start: ISO 8601 start of the "last detected" time range. Omit for no lower bound.
        last_detected_end: ISO 8601 end of the "last detected" time range. Omit to default to "now".
        first_seen_start: ISO 8601 start of the "first seen" time range. Omit for no lower bound.
        first_seen_end: ISO 8601 end of the "first seen" time range. Omit to default to "now".
    """
    try:
        return await client.list_attack_surface_devices(
            order_by=order_by,
            filter_query=filter_query,
            top=top,
            last_detected_start=last_detected_start,
            last_detected_end=last_detected_end,
            first_seen_start=first_seen_start,
            first_seen_end=first_seen_end,
        )
    except VisionOneApiError as exc:
        logger.warning("crem_discovered_devices_list failed: %s", exc)
        raise


@mcp.tool()
async def crem_user_risk_profile_get(user_id: str) -> dict[str, Any]:
    """Get the full Trend Vision One risk profile for a single user, including their overall
    riskScore and the individual riskyEvents that contributed to it.

    Args:
        user_id: The user's ID (as returned by crem_high_risk_users_list).
    """
    try:
        return await client.get_high_risk_user(user_id)
    except VisionOneApiError as exc:
        logger.warning("crem_user_risk_profile_get failed: %s", exc)
        raise


@mcp.tool()
async def crem_device_risk_profile_get(
    device_id: str, risky_event_score: int | None = None
) -> dict[str, Any]:
    """Get the full Trend Vision One risk profile for a single device, including its risk
    factors and vulnerabilities.

    Args:
        device_id: The device's ID (as returned by crem_vulnerable_devices_list or
            crem_discovered_devices_list).
        risky_event_score: Optional minimum score to filter which risky events are included
            in the response.
    """
    try:
        return await client.get_high_risk_device(device_id, risky_event_score=risky_event_score)
    except VisionOneApiError as exc:
        logger.warning("crem_device_risk_profile_get failed: %s", exc)
        raise


async def _healthz(_request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_app():
    """Build the ASGI app: FastMCP's Streamable HTTP app, plus /healthz and (optionally) bearer auth.

    Auth is skipped entirely when MCP_REQUIRE_AUTH=false. That's needed for clients like
    ChatGPT's Developer Mode, whose custom connectors only support OAuth or no-auth --
    there's no way to hand it a static bearer token the way Claude Desktop's custom
    connector accepts one. Only run this way on a network you trust.
    """
    app = mcp.streamable_http_app()
    app.router.routes.insert(0, Route("/healthz", _healthz))
    if settings.require_auth:
        app.add_middleware(BearerAuthMiddleware, expected_token=settings.mcp_bearer_token)
    else:
        logger.warning(
            "MCP_REQUIRE_AUTH=false -- this server is accepting UNAUTHENTICATED requests. "
            "Anyone who can reach it can read Vision One Workbench/Threat Intel data through "
            "it. Only do this for local/trusted-network testing (e.g. ChatGPT Developer Mode)."
        )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
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
