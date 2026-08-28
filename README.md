# vision-one-mcp-python

A from-scratch Python [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
[Trend Vision One](https://www.trendmicro.com/en_us/business/products/detection-response/xdr.html), built as a
learning project to get hands-on with MCP, containerized Python services, and remote deployment — currently
scoped to Docker (no Kubernetes for now).

> Trend Micro publishes an official Go-based MCP server ([trendmicro/vision-one-mcp-server](https://github.com/trendmicro/vision-one-mcp-server))
> that covers far more of the API surface. This project is intentionally a from-scratch, read-only, learning-focused
> reimplementation in Python — not a replacement for the official server.

## What this is

- **Language:** Python (using the official [`mcp`](https://github.com/modelcontextprotocol/python-sdk) SDK's `FastMCP`)
- **Transport:** Streamable HTTP (required for remote/hosted MCP servers — Claude Desktop's custom connectors
  do not support stdio for remote servers)
- **Auth:** Static bearer token by default (checked by a small ASGI middleware), or fully disabled via
  `MCP_REQUIRE_AUTH=false` for clients that can't present one (see
  [Connecting ChatGPT](#connecting-chatgpt-developer-mode) below)
- **Packaging:** Just Docker — a single container plus [Caddy](https://caddyserver.com/) as a reverse proxy
  for automatic HTTPS. No Kubernetes/Helm for now.

## Available tools

Everything this server exposes is read-only — there is no code path anywhere in this repo that can change,
create, or delete anything in Vision One.

| Tool | Vision One area | What it does |
| --- | --- | --- |
| `workbench_alerts_list` | Workbench | List alerts, optionally filtered by time range and investigation status |
| `workbench_alert_detail_get` | Workbench | Get full detail for a single alert by ID |
| `threatintel_suspicious_objects_list` | Threat Intelligence | List entries in the Suspicious Object List (domains, IPs, file hashes, URLs, email addresses) |
| `threatintel_suspicious_object_exceptions_list` | Threat Intelligence | List entries in the Exception List (objects explicitly excluded from suspicious-object matching) |
| `endpoint_security_endpoints_list` | Endpoint Security | List managed endpoints/devices, with sorting, field selection, and filtering |
| `crem_vulnerable_devices_list` | Cyber Risk Exposure Management (CREM) | List devices with detected vulnerabilities (CVEs), with sorting and filtering |
| `crem_high_risk_users_list` | Cyber Risk Exposure Management (CREM) | List users with elevated risk scores, including the risky events (e.g. leaked credentials, account compromise) behind each score |
| `crem_discovered_domain_accounts_list` | Cyber Risk Exposure Management (CREM) | List domain accounts discovered via Attack Surface Risk Management asset discovery |
| `crem_discovered_devices_list` | Cyber Risk Exposure Management (CREM) | List devices discovered via Attack Surface Risk Management asset discovery, with optional last-detected/first-seen date filtering |

All list tools accept a `top` parameter capping how many results come back (default 50), and most accept a raw
`filter_query` string passed straight through as Vision One's `TMV1-Filter` header for further narrowing.

## Vision One API key permissions required

The API key configured via `VISION_ONE_API_KEY` needs read access to each area a tool touches. In the Vision One
role editor:

- **Workbench** — view access, for `workbench_alerts_list` / `workbench_alert_detail_get`
- **Threat Intelligence** — view access, for both `threatintel_*` tools
- **Dashboards & Reports → Reports** — **View**, **Configure and download** — required for
  `endpoint_security_endpoints_list` and `crem_vulnerable_devices_list`. This was confirmed directly against a
  live tenant; it's not the permission category you'd necessarily expect for endpoint/device data, but it's
  what these two calls actually require. Every call this project makes against it is a plain HTTP GET regardless
  of what the permission is named. `crem_high_risk_users_list`, `crem_discovered_domain_accounts_list`, and
  `crem_discovered_devices_list` all hit the same `/v3.0/asrm/*` API family, so they likely need this same
  permission — not yet confirmed against a live tenant, so verify before relying on it.

Give the key the minimum above rather than a broad/admin role — this server only ever issues GET requests, so it
never needs write permissions anywhere.

## Why Streamable HTTP (not Lambda)

MCP's remote transport is a long-lived, potentially streaming HTTP connection. AWS Lambda is a poor fit for
that — it's a short-lived, 15-minute-max function invocation model, not a persistent server. A plain Docker
container keeps a warm process with open connections, which is what Streamable HTTP wants.

## Architecture

```
Claude Desktop / ChatGPT (remote MCP client)
        |  HTTPS + Bearer token (or no auth, see below)
        v
Caddy (automatic TLS via Let's Encrypt)
        |
        v
vision-one-mcp-python container
   - Streamable HTTP MCP server (FastMCP)
   - Bearer-token auth middleware (optional)
   - CORS middleware (for browser-based MCP clients)
        |  HTTPS + Vision One API key
        v
Trend Vision One REST API (api.<region>.xdr.trendmicro.com)
```

See `docs/architecture.md` for the full diagram and data flow notes, including why DNS-rebinding protection had
to be explicitly disabled for this to work behind a real domain at all.

## Repo layout

```
src/vision_one_mcp/     Python package: MCP server, Vision One client, auth middleware, config
Dockerfile              Container image build
docker-compose.yml      App container + Caddy reverse proxy (local dev or production)
Caddyfile               Caddy config: reverse proxy + automatic HTTPS
docs/                   Architecture notes and diagram
```

## Quickstart (local)

```bash
cp .env.example .env
# edit .env: set VISION_ONE_API_KEY, VISION_ONE_REGION, MCP_BEARER_TOKEN

pip install -e .
python -m vision_one_mcp.server
# server listening on http://0.0.0.0:8000/mcp
```

## Running in Docker

Standalone, without Caddy/TLS (fine for local testing over plain HTTP):

```bash
docker build -t vision-one-mcp-python:latest .
docker run --rm -p 8000:8000 --env-file .env vision-one-mcp-python:latest
```

With Caddy in front (the production setup — automatic HTTPS via Let's Encrypt):

```bash
cp .env.example .env
# edit .env, including CADDY_DOMAIN and CADDY_EMAIL

docker compose up -d --build
docker compose logs -f caddy   # watch it obtain the certificate
```

Point DNS for `CADDY_DOMAIN` at the host before starting Caddy, and open ports 80 (ACME HTTP-01 challenge) and
443 (the actual MCP endpoint) in the security group. The app container never publishes a port to the host
directly — only Caddy is internet-facing.

## Connecting Claude Desktop

Custom connectors via remote MCP require a **public HTTPS URL** — plain HTTP or a self-signed cert will not
validate.

1. In Claude Desktop: **Settings → Connectors → Add custom connector**
2. URL: `https://<your-host>/mcp`
3. Advanced settings → set the bearer token you configured as the connector's auth header
   (`Authorization: Bearer <MCP_BEARER_TOKEN>`)

Requires org/admin permission to add custom connectors in some Claude workspaces — if you don't have that, see
the ChatGPT path below instead.

## Connecting ChatGPT (Developer Mode)

ChatGPT speaks the same Streamable HTTP MCP transport, but its Developer Mode custom connectors only support
**OAuth or no-auth** — not a static bearer token. For this project, run with auth switched off:

```bash
# in .env
MCP_REQUIRE_AUTH=false
```

Then in ChatGPT: Settings → Apps & Connectors → Advanced → Developer mode → add a custom connector pointing at
`https://<your-host>/mcp`, authentication set to **No authentication**.

**If you add or change tools later and ChatGPT keeps showing the old list:** this server declares
`listChanged: false` at the MCP protocol level, meaning it tells clients up front not to expect the tool list to
change mid-session — so ChatGPT has no reason to re-fetch it once a connector session is established. Remove
and re-add the connector (not just start a new chat) to force a fresh handshake and pick up new tools.

Running without auth means anyone who can reach the URL can call every tool above — fine for short-lived testing
against a domain only you know about, not something to leave running long-term.

## Security notes

- Read-only by design: no write/action path to Vision One exists anywhere in this codebase.
- The Vision One API key and the MCP bearer token are both secrets, loaded from `.env` — never commit the real
  `.env` file (it's gitignored).
- `MCP_REQUIRE_AUTH=false` removes the only protection this server has — treat it as a deliberate, temporary
  testing choice, not a default.
- This is a personal learning project, not an officially supported Trend Micro integration. For production use,
  prefer the [official Vision One MCP server](https://github.com/trendmicro/vision-one-mcp-server).

## License

MIT — see [LICENSE](LICENSE).
