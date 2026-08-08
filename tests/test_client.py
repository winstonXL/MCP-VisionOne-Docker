"""Unit tests for VisionOneClient. Everything is mocked via respx — no live API calls."""

from __future__ import annotations

import httpx
import pytest
import respx

from vision_one_mcp.client import VisionOneApiError, VisionOneClient, _filter_eq, _to_utc_iso

BASE_URL = "https://api.xdr.trendmicro.com"


@pytest.fixture
def client() -> VisionOneClient:
    return VisionOneClient(api_key="test-key", base_url=BASE_URL)


def test_filter_eq_single_value():
    assert _filter_eq("investigationStatus", "New") == "investigationStatus eq 'New'"


def test_filter_eq_multiple_values():
    result = _filter_eq("investigationStatus", ["New", "In Progress"])
    assert result == "(investigationStatus eq 'New' or investigationStatus eq 'In Progress')"


def test_to_utc_iso_from_string():
    assert _to_utc_iso("2026-08-01T00:00:00+00:00") == "2026-08-01T00:00:00Z"


@pytest.mark.asyncio
@respx.mock
async def test_list_workbench_alerts_sends_bearer_token_and_filter(client: VisionOneClient):
    route = respx.get(f"{BASE_URL}/v3.0/workbench/alerts").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "alert-1"}]})
    )

    result = await client.list_workbench_alerts(investigation_status="New", top=10)

    assert result == [{"id": "alert-1"}]
    sent_request = route.calls[0].request
    assert sent_request.headers["Authorization"] == "Bearer test-key"
    assert sent_request.headers["TMV1-Filter"] == "investigationStatus eq 'New'"


@pytest.mark.asyncio
@respx.mock
async def test_list_workbench_alerts_follows_pagination(client: VisionOneClient):
    next_link = f"{BASE_URL}/v3.0/workbench/alerts?page=2"

    # A single route matching the base path handles both the first request and the
    # follow-up request to `nextLink` (respx matches on path, not query string), so a
    # side_effect list lets us return a different page on each successive call.
    respx.get(f"{BASE_URL}/v3.0/workbench/alerts").mock(
        side_effect=[
            httpx.Response(200, json={"items": [{"id": "a"}], "nextLink": next_link}),
            httpx.Response(200, json={"items": [{"id": "b"}]}),
        ]
    )

    result = await client.list_workbench_alerts()

    assert [item["id"] for item in result] == ["a", "b"]


@pytest.mark.asyncio
@respx.mock
async def test_list_workbench_alerts_respects_max_items(client: VisionOneClient):
    respx.get(f"{BASE_URL}/v3.0/workbench/alerts").mock(
        return_value=httpx.Response(
            200, json={"items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
        )
    )

    result = await client.list_workbench_alerts(top=2)

    assert len(result) == 2


@pytest.mark.asyncio
@respx.mock
async def test_get_workbench_alert_detail(client: VisionOneClient):
    respx.get(f"{BASE_URL}/v3.0/workbench/alerts/alert-123").mock(
        return_value=httpx.Response(200, json={"id": "alert-123", "severity": "high"})
    )

    result = await client.get_workbench_alert("alert-123")

    assert result["id"] == "alert-123"


@pytest.mark.asyncio
@respx.mock
async def test_non_200_response_raises_vision_one_api_error(client: VisionOneClient):
    respx.get(f"{BASE_URL}/v3.0/workbench/alerts/missing").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )

    with pytest.raises(VisionOneApiError) as exc_info:
        await client.get_workbench_alert("missing")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_list_suspicious_objects(client: VisionOneClient):
    respx.get(f"{BASE_URL}/v3.0/threatintel/suspiciousObjects").mock(
        return_value=httpx.Response(200, json={"items": [{"type": "ip", "value": "1.2.3.4"}]})
    )

    result = await client.list_suspicious_objects()

    assert result == [{"type": "ip", "value": "1.2.3.4"}]


@pytest.mark.asyncio
@respx.mock
async def test_list_suspicious_object_exceptions(client: VisionOneClient):
    respx.get(f"{BASE_URL}/v3.0/threatintel/suspiciousObjectExceptions").mock(
        return_value=httpx.Response(200, json={"items": [{"type": "domain", "value": "example.com"}]})
    )

    result = await client.list_suspicious_object_exceptions()

    assert result == [{"type": "domain", "value": "example.com"}]
