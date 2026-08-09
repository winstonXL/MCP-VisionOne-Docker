# Architecture

![request flow](architecture.svg)

## Components

- **Claude Desktop** — connects as a remote MCP custom connector over HTTPS. Sends an
  `Authorization: Bearer <token>` header on every request; has no direct knowledge of
  Vision One at all, only of the tools this server exposes.
- **Caddy** — reverse proxy and TLS terminator, running as its own container. Claude
  Desktop's custom connector will not accept a self-signed certificate, so this needs a
  certificate from a publicly trusted CA — Caddy obtains and renews one automatically
  from Let's Encrypt via the HTTP-01 challenge, as long as DNS for the configured
  hostname points at the host (see [`deploy/ec2/README.md`](../deploy/ec2/README.md)).
- **vision-one-mcp container** — the actual server. Two layers inside:
  1. `BearerAuthMiddleware` (plain ASGI middleware, checked before anything else,
     `/healthz` excepted for the container healthcheck) rejects any request that
     doesn't present the configured shared secret — *unless* `MCP_REQUIRE_AUTH=false`,
     in which case this layer is skipped entirely (see "Auth is configurable" below).
  2. `FastMCP` — registers the four read-only tools and speaks Streamable HTTP.
  This container is never exposed directly to the host or the internet — only Caddy
  publishes ports 80/443; the app is reachable solely through Caddy's internal
  `reverse_proxy` over the Docker Compose network.
- **`.env`** — the Vision One API key, the MCP bearer token, and region/domain config,
  loaded as environment variables. Never baked into the image, never committed.
- **Trend Vision One** — the actual data source. The container calls out to
  `api.<region>.xdr.trendmicro.com` with the Vision One API key as its own bearer token
  — a second, separate credential from the one Claude Desktop uses to talk to *this*
  server.

## Two independent trust boundaries

It's worth being explicit that there are two different bearer tokens doing two
different jobs, because it's easy to conflate them:

1. **Claude Desktop ↔ this server**: the `MCP_BEARER_TOKEN` you generate yourself and
   configure in both places. Proves to this server that a request is from *your*
   Claude Desktop, not a random client that found the URL.
2. **This server ↔ Trend Vision One**: the `VISION_ONE_API_KEY` from your Vision One
   tenant. Proves to Vision One that this server is allowed to read Workbench/Threat
   Intel data.

Compromising one does not automatically expose the other — but this server does hold
both secrets in memory, so the container itself is the thing to lock down: least-
privilege API key permissions, a non-root user in the image (see `Dockerfile`), and
never exposing the app port directly to the internet (Caddy is the only public-facing
process).

## Auth is configurable, because MCP clients disagree on what they support

Claude Desktop's custom connectors can be configured with a static bearer token, which
is what `BearerAuthMiddleware` was built around. ChatGPT's Developer Mode custom
connectors cannot present a static token at all — only OAuth or no-auth. Rather than
fork the app per client, `MCP_REQUIRE_AUTH` toggles the middleware on/off at startup:

- `MCP_REQUIRE_AUTH=true` (default): the "Two independent trust boundaries" section
  above applies as written.
- `MCP_REQUIRE_AUTH=false`: the client ↔ server boundary disappears entirely — the
  server accepts any request that reaches it. The server ↔ Vision One boundary (the
  API key) is unaffected either way. This mode exists for testing against clients like
  ChatGPT that can't do better yet; a real multi-client setup would eventually want
  OAuth instead of this binary switch.

## Why not Lambda / EventBridge / SNS here

An earlier direction for this project explored Vision One's S3-based SIEM export
combined with EventBridge, SNS, and Lambda for an event-driven ingestion pipeline.
That's still a reasonable design — for *that* problem. It doesn't fit *this* problem:
Claude Desktop's remote MCP transport needs a long-lived, addressable HTTP endpoint
that can hold a streaming connection open, which is a server model, not a
function-invocation model. Lambda's 15-minute execution cap and non-persistent nature
fight against that; a small always-on container is the natural fit instead.

## Why not Kubernetes (for now)

An earlier pass at this also built out a Helm chart for deployment on a k3s cluster,
with the idea of making it portable to customers running their own Kubernetes. That's
parked for now in favor of getting the simpler Docker Compose + Caddy setup solid
first — one container plus a reverse proxy is enough infrastructure to reason about
while still learning the MCP/auth/deployment pieces. Kubernetes may come back later if
there's a real need for it (multiple replicas, rolling updates, etc.); the app itself
doesn't assume anything about its runtime, so re-introducing it later is mostly a
matter of writing new manifests, not changing code.

## Read-only by design

There is no code path in this repository that can modify anything in Vision One. The
`VisionOneClient` in `src/vision_one_mcp/client.py` only implements GET requests. If
this project grows write/action tools later (isolating an endpoint, adding a
suspicious object), they should be added behind an explicit `readonly` flag, mirroring
the pattern the official [vision-one-mcp-server](https://github.com/trendmicro/vision-one-mcp-server)
uses.
