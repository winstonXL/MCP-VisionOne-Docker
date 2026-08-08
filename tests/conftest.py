"""Shared pytest fixtures."""

import pytest

# httpx honors ambient proxy env vars (trust_env=True by default), which is the right
# behavior in production (some customer networks require an egress proxy to reach
# Vision One), but it means these unit tests can be affected by whatever proxy env vars
# happen to be set on the machine running them. Since every test here mocks the HTTP
# layer with respx and should never depend on real network config, strip proxy env vars
# for the duration of the test session.
_PROXY_ENV_VARS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
    "http_proxy", "https_proxy", "all_proxy", "no_proxy",
)


@pytest.fixture(autouse=True)
def _no_ambient_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in _PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
