"""Minimal, read-only async client for the Trend Vision One REST API (v3).

Deliberately small: this only implements the handful of endpoints the MCP server in
this project exposes as tools. Modeled on Trend Micro's own API cookbook
(https://github.com/trendmicro/tm-v1-api-cookbook/blob/main/detection-and-response/python/detection_and_response.py),
trimmed down to GET-only calls:

  - GET /v3.0/workbench/alerts                     (paginated list, with time-range + filter support)
  - GET /v3.0/workbench/alerts/{id}                 (single alert detail)
  - GET /v3.0/threatintel/suspiciousObjects         (Suspicious Object List, paginated)
  - GET /v3.0/threatintel/suspiciousObjectExceptions (Exception List, paginated)
  - GET /v3.0/endpointSecurity/endpoints            (managed endpoints/devices, paginated)
  - GET /v3.0/asrm/vulnerableDevices                (devices with detected CVEs, paginated)
  - GET /v3.0/asrm/highRiskUsers                    (users with elevated risk scores, paginated)
  - GET /v3.0/asrm/attackSurfaceDomainAccounts       (discovered domain accounts, paginated)
  - GET /v3.0/asrm/attackSurfaceDevices              (discovered devices, paginated)
  - GET /v3.0/asrm/highRiskUsers/{id}                (single user risk profile)
  - GET /v3.0/asrm/highRiskDevices/{id}              (single device risk profile)

No write/action endpoints (e.g. isolating an endpoint, adding a suspicious object, updating
alert status) are implemented here on purpose — this server is read-only by design.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Iterable

import httpx

DEFAULT_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DEFAULT_PAGE_SIZE = 50
MAX_PAGES = 20  # safety cap so pagination can't hang a tool call indefinitely


class VisionOneApiError(RuntimeError):
    """Raised when the Vision One API returns a non-2xx response."""

    def __init__(self, method: str, path: str, status_code: int, body: str):
        super().__init__(f"{method} {path} failed: {status_code} {body}")
        self.status_code = status_code
        self.body = body


def _to_utc_iso(value: str | dt.datetime) -> str:
    """Normalize a datetime (or ISO string) to the Zulu format the Vision One API expects."""
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value)
    if value.tzinfo is None:
        value = value.astimezone()
    value = value.astimezone(dt.timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _filter_eq(field: str, values: Iterable[str] | str) -> str:
    """Build a `field eq 'a' or field eq 'b'` TMV1-Filter fragment."""
    if isinstance(values, str):
        values = [values]
    else:
        values = list(values)
    clause = " or ".join(f"{field} eq '{v}'" for v in values)
    return f"({clause})" if len(values) > 1 else clause


class VisionOneClient:
    """Thin async wrapper around the subset of the Vision One v3 REST API this server uses."""

    def __init__(self, api_key: str, base_url: str, timeout: httpx.Timeout = DEFAULT_TIMEOUT):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "vision-one-mcp-python/0.1.0",
        }
        self._timeout = timeout

    async def _get(
        self,
        client: httpx.AsyncClient,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = path_or_url if path_or_url.startswith("http") else f"{self._base_url}{path_or_url}"
        merged_headers = {**self._headers, **(headers or {})}
        resp = await client.get(url, params=params, headers=merged_headers, timeout=self._timeout)
        if resp.status_code != 200:
            raise VisionOneApiError("GET", path_or_url, resp.status_code, resp.text[:500])
        return resp.json()

    async def _get_items(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        max_items: int | None = None,
    ) -> list[dict[str, Any]]:
        """Follow `nextLink` pagination and return a flat list of `items`, capped at max_items."""
        items: list[dict[str, Any]] = []
        next_link: str | None = None
        pages = 0
        async with httpx.AsyncClient() as client:
            while True:
                pages += 1
                if pages > MAX_PAGES:
                    break
                if next_link is None:
                    data = await self._get(client, path, params=params, headers=headers)
                else:
                    data = await self._get(client, next_link, headers=headers)
                items.extend(data.get("items", []))
                if max_items is not None and len(items) >= max_items:
                    return items[:max_items]
                next_link = data.get("nextLink")
                if not next_link:
                    break
        return items

    # -- Workbench -----------------------------------------------------------------

    async def list_workbench_alerts(
        self,
        *,
        start: str | None = None,
        end: str | None = None,
        investigation_status: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if start:
            params["startDateTime"] = _to_utc_iso(start)
        if end:
            params["endDateTime"] = _to_utc_iso(end)

        headers: dict[str, str] = {}
        if investigation_status:
            headers["TMV1-Filter"] = _filter_eq("investigationStatus", investigation_status)

        return await self._get_items(
            "/v3.0/workbench/alerts", params=params, headers=headers, max_items=top
        )

    async def get_workbench_alert(self, alert_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient() as client:
            return await self._get(client, f"/v3.0/workbench/alerts/{alert_id}")

    # -- Threat Intelligence ---------------------------------------------------------

    async def list_suspicious_objects(self, *, top: int = DEFAULT_PAGE_SIZE) -> list[dict[str, Any]]:
        return await self._get_items("/v3.0/threatintel/suspiciousObjects", max_items=top)

    async def list_suspicious_object_exceptions(
        self, *, top: int = DEFAULT_PAGE_SIZE
    ) -> list[dict[str, Any]]:
        return await self._get_items("/v3.0/threatintel/suspiciousObjectExceptions", max_items=top)

    # -- Endpoint Security -----------------------------------------------------------

    async def list_endpoints(
        self,
        *,
        order_by: str | None = None,
        select: str | None = None,
        filter_query: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """List managed endpoints (devices) known to Vision One Endpoint Security."""
        params: dict[str, Any] = {"top": top}
        if order_by:
            params["orderBy"] = order_by
        if select:
            params["select"] = select

        headers: dict[str, str] = {}
        if filter_query:
            headers["TMV1-Filter"] = filter_query

        return await self._get_items(
            "/v3.0/endpointSecurity/endpoints", params=params, headers=headers, max_items=top
        )

    # -- Cyber Risk Exposure Management (CREM / ASRM) --------------------------------

    async def list_vulnerable_devices(
        self,
        *,
        order_by: str | None = None,
        cve_detection_status: str | None = None,
        filter_query: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """List devices with detected vulnerabilities (CVEs), per Attack Surface Risk Management."""
        params: dict[str, Any] = {"top": top}
        if order_by:
            params["orderBy"] = order_by
        if cve_detection_status:
            params["cveDetectionStatus"] = cve_detection_status

        headers: dict[str, str] = {}
        if filter_query:
            headers["TMV1-Filter"] = filter_query

        return await self._get_items(
            "/v3.0/asrm/vulnerableDevices", params=params, headers=headers, max_items=top
        )

    async def list_high_risk_users(
        self,
        *,
        order_by: str | None = None,
        filter_query: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """List users with elevated Vision One risk scores, per Attack Surface Risk Management.

        Each entry includes the user's overall riskScore plus the individual riskyEvents
        (e.g. leaked credentials, account compromise indicators) that contributed to it.
        """
        params: dict[str, Any] = {"top": top}
        if order_by:
            params["orderBy"] = order_by

        headers: dict[str, str] = {}
        if filter_query:
            headers["TMV1-Filter"] = filter_query

        return await self._get_items(
            "/v3.0/asrm/highRiskUsers", params=params, headers=headers, max_items=top
        )

    async def list_attack_surface_domain_accounts(
        self,
        *,
        order_by: str | None = None,
        filter_query: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
    ) -> list[dict[str, Any]]:
        """List domain accounts discovered by Attack Surface Risk Management."""
        params: dict[str, Any] = {"top": top}
        if order_by:
            params["orderBy"] = order_by

        headers: dict[str, str] = {}
        if filter_query:
            headers["TMV1-Filter"] = filter_query

        return await self._get_items(
            "/v3.0/asrm/attackSurfaceDomainAccounts", params=params, headers=headers, max_items=top
        )

    async def list_attack_surface_devices(
        self,
        *,
        order_by: str | None = None,
        filter_query: str | None = None,
        top: int = DEFAULT_PAGE_SIZE,
        last_detected_start: str | None = None,
        last_detected_end: str | None = None,
        first_seen_start: str | None = None,
        first_seen_end: str | None = None,
    ) -> list[dict[str, Any]]:
        """List devices discovered by Attack Surface Risk Management (asset discovery)."""
        params: dict[str, Any] = {"top": top}
        if order_by:
            params["orderBy"] = order_by
        if last_detected_start:
            params["lastDetectedStartDateTime"] = _to_utc_iso(last_detected_start)
        if last_detected_end:
            params["lastDetectedEndDateTime"] = _to_utc_iso(last_detected_end)
        if first_seen_start:
            params["firstSeenStartDateTime"] = _to_utc_iso(first_seen_start)
        if first_seen_end:
            params["firstSeenEndDateTime"] = _to_utc_iso(first_seen_end)

        headers: dict[str, str] = {}
        if filter_query:
            headers["TMV1-Filter"] = filter_query

        return await self._get_items(
            "/v3.0/asrm/attackSurfaceDevices", params=params, headers=headers, max_items=top
        )

    async def get_high_risk_user(self, user_id: str) -> dict[str, Any]:
        """Get the full risk profile for a single user."""
        async with httpx.AsyncClient() as client:
            return await self._get(client, f"/v3.0/asrm/highRiskUsers/{user_id}")

    async def get_high_risk_device(
        self, device_id: str, *, risky_event_score: int | None = None
    ) -> dict[str, Any]:
        """Get the full risk profile for a single device."""
        params: dict[str, Any] = {}
        if risky_event_score is not None:
            params["riskyEventScore"] = risky_event_score

        async with httpx.AsyncClient() as client:
            return await self._get(
                client, f"/v3.0/asrm/highRiskDevices/{device_id}", params=params
            )
