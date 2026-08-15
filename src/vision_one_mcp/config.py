"""Configuration loading for the Vision One MCP server.

Everything is read from the environment (see .env.example). In Docker Compose these
come from `env_file: .env`; locally, load a .env file the same way.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

REGION_BASE_URLS: dict[str, str] = {
    "us": "https://api.xdr.trendmicro.com",
    "eu": "https://api.eu.xdr.trendmicro.com",
    "au": "https://api.au.xdr.trendmicro.com",
    "jp": "https://api.jp.xdr.trendmicro.com",
    "sg": "https://api.sg.xdr.trendmicro.com",
    "in": "https://api.in.xdr.trendmicro.com",
    "mea": "https://api.mea.xdr.trendmicro.com",
}

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Settings:
    vision_one_api_key: str
    vision_one_base_url: str
    require_auth: bool
    mcp_bearer_token: str | None
    host: str
    port: int


def _resolve_base_url() -> str:
    override = os.environ.get("VISION_ONE_BASE_URL")
    if override:
        return override.rstrip("/")

    region = os.environ.get("VISION_ONE_REGION", "us").strip().lower()
    try:
        return REGION_BASE_URLS[region]
    except KeyError as exc:
        valid = ", ".join(sorted(REGION_BASE_URLS))
        raise ConfigError(
            f"Unknown VISION_ONE_REGION '{region}'. Valid regions: {valid}. "
            "Set VISION_ONE_BASE_URL directly to override (e.g. for gov/internal endpoints)."
        ) from exc


def _parse_bool(raw: str, *, default: bool, var_name: str) -> bool:
    value = raw.strip().lower()
    if not value:
        return default
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise ConfigError(
        f"{var_name}='{raw}' is not a valid boolean. Use one of: "
        f"{', '.join(sorted(_TRUE_VALUES | _FALSE_VALUES))}."
    )


def load_settings() -> Settings:
    api_key = os.environ.get("VISION_ONE_API_KEY", "")
    if not api_key or api_key == "changeme":
        raise ConfigError(
            "VISION_ONE_API_KEY is not set. Copy .env.example to .env (or set the "
            "container env var) and provide a real Vision One API key."
        )

    require_auth = _parse_bool(
        os.environ.get("MCP_REQUIRE_AUTH", ""), default=True, var_name="MCP_REQUIRE_AUTH"
    )

    bearer_token = os.environ.get("MCP_BEARER_TOKEN", "")
    if require_auth:
        if not bearer_token or bearer_token == "changeme":
            raise ConfigError(
                "MCP_BEARER_TOKEN is not set. This is the shared secret a client (e.g. "
                "Claude Desktop) must send back to this server — generate a random value, "
                "e.g. `openssl rand -hex 32`. If you're intentionally running without auth "
                "(e.g. for ChatGPT Developer Mode, which can't present a static token), set "
                "MCP_REQUIRE_AUTH=false instead — only do this on a network you trust."
            )
    else:
        bearer_token = bearer_token or None

    return Settings(
        vision_one_api_key=api_key,
        vision_one_base_url=_resolve_base_url(),
        require_auth=require_auth,
        mcp_bearer_token=bearer_token,
        host=os.environ.get("MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("MCP_PORT", "8000")),
    )
