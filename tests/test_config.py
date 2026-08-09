"""Unit tests for config loading."""

from __future__ import annotations

import pytest

from vision_one_mcp import config


def test_resolve_base_url_from_region(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_REGION", "eu")
    monkeypatch.delenv("VISION_ONE_BASE_URL", raising=False)
    assert config._resolve_base_url() == "https://api.eu.xdr.trendmicro.com"


def test_resolve_base_url_override(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_BASE_URL", "https://internal.example.com/")
    assert config._resolve_base_url() == "https://internal.example.com"


def test_resolve_base_url_unknown_region_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_REGION", "atlantis")
    monkeypatch.delenv("VISION_ONE_BASE_URL", raising=False)
    with pytest.raises(config.ConfigError):
        config._resolve_base_url()


def test_load_settings_requires_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VISION_ONE_API_KEY", raising=False)
    monkeypatch.setenv("MCP_BEARER_TOKEN", "some-token")
    with pytest.raises(config.ConfigError):
        config.load_settings()


def test_load_settings_requires_bearer_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.delenv("MCP_BEARER_TOKEN", raising=False)
    with pytest.raises(config.ConfigError):
        config.load_settings()


def test_load_settings_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.setenv("MCP_BEARER_TOKEN", "real-token")
    monkeypatch.setenv("VISION_ONE_REGION", "us")
    settings = config.load_settings()
    assert settings.vision_one_api_key == "real-key"
    assert settings.vision_one_base_url == "https://api.xdr.trendmicro.com"


def test_load_settings_no_auth_allows_missing_bearer_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.setenv("MCP_REQUIRE_AUTH", "false")
    monkeypatch.delenv("MCP_BEARER_TOKEN", raising=False)
    settings = config.load_settings()
    assert settings.require_auth is False
    assert settings.mcp_bearer_token is None


def test_load_settings_no_auth_still_accepts_a_token_if_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.setenv("MCP_REQUIRE_AUTH", "false")
    monkeypatch.setenv("MCP_BEARER_TOKEN", "real-token")
    settings = config.load_settings()
    assert settings.mcp_bearer_token == "real-token"


def test_load_settings_default_require_auth_is_true(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.setenv("MCP_BEARER_TOKEN", "real-token")
    monkeypatch.delenv("MCP_REQUIRE_AUTH", raising=False)
    settings = config.load_settings()
    assert settings.require_auth is True


def test_parse_bool_invalid_value_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VISION_ONE_API_KEY", "real-key")
    monkeypatch.setenv("MCP_REQUIRE_AUTH", "maybe")
    with pytest.raises(config.ConfigError):
        config.load_settings()
