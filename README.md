# vision-one-mcp-python

A from-scratch Python [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for
[Trend Vision One](https://www.trendmicro.com/en_us/business/products/detection-response/xdr.html), built as a
learning project to get hands-on with MCP, containerized Python services, and Kubernetes deployment patterns
that work identically on AWS EC2 and on customer on-prem clusters.

> Trend Micro publishes an official Go-based MCP server ([trendmicro/vision-one-mcp-server](https://github.com/trendmicro/vision-one-mcp-server))
> that covers far more of the API surface. This project is intentionally a from-scratch, read-only, learning-focused
> reimplementation in Python — not a replacement for the official server.

## What this is

- **Language:** Python (using the official [`mcp`](https://github.com/modelcontextprotocol/python-sdk) SDK's `FastMCP`)
- **Transport:** Streamable HTTP (required for remote/hosted MCP servers — Claude Desktop's custom connectors
  do not support stdio for remote servers)
- **Auth:** Static bearer token, checked by a small ASGI middleware in front of the MCP app
- **Scope (v0.1):** Read-only tools against two Vision One API domains:
  - **Workbench** — list alerts, get alert detail
  - **Threat Intelligence** — list Suspicious Object List entries, list Threat Intelligence Feed indicators
- **Packaging:** Docker image + Helm chart, deployable the same way on:
  - A self-managed Kubernetes cluster (k3s) on an AWS EC2 instance (how this project is hosted)
  - Any customer's own Kubernetes cluster (k3s, kubeadm, EKS, etc.) — no AWS dependency at runtime

## Why Streamable HTTP + Kubernetes (not Lambda)

MCP's remote transport is a long-lived, potentially streaming HTTP connection. AWS Lambda is a poor fit for that —
it's a short-lived, 15-minute-max function invocation model, not a persistent server. A container running on
Kubernetes (or plain Docker) keeps a warm process with open connections, which is what Streamable HTTP wants.
That also happens to be exactly what makes this deployable both on AWS EC2 and on a customer's local cluster with
zero changes to the app itself.

## Architecture

```
Claude Desktop (remote MCP custom connector)
        |  HTTPS + Bearer token
        v
Ingress (TLS termination)
        |
        v
Kubernetes Service
        |
        v
vision-one-mcp-python Pod(s)
   - Streamable HTTP MCP server (FastMCP)
   - Bearer-token auth middleware
        |  HTTPS + Vision One API key
        v
Trend Vision One REST API (api.<region>.xdr.trendmicro.com)
```

See [docs/architecture.md](docs/architecture.md) for the full diagram and data flow notes.

## Repo layout

```
src/vision_one_mcp/     Python package: MCP server, Vision One client, auth middleware, config
tests/                  Unit tests (mocked HTTP, no live Vision One calls)
Dockerfile              Container image build
docker-compose.yml      Local run for development
deploy/helm/            Helm chart — the deployment artifact for both AWS EC2 and customer clusters
deploy/ec2/             Guide + script for standing up a single-node k3s cluster on an EC2 instance
docs/                   Architecture notes and diagram
```

## Quickstart (local)

```bash
cp .env.example .env
# edit .env: set VISION_ONE_API_KEY, VISION_ONE_REGION, MCP_BEARER_TOKEN

pip install -e ".[dev]"
python -m vision_one_mcp.server
# server listening on http://0.0.0.0:8000/mcp
```

Run the test suite (no live API calls, everything is mocked):

```bash
pytest
```

## Running in Docker

```bash
docker build -t vision-one-mcp-python:latest .
docker run --rm -p 8000:8000 --env-file .env vision-one-mcp-python:latest
```

## Connecting Claude Desktop

Custom connectors via remote MCP require a **public HTTPS URL** — plain HTTP or a self-signed cert will not
validate. For local testing before you have real TLS, tunnel it (e.g. `ngrok http 8000`) or use the
[`mcp-remote`](https://github.com/geelen/mcp-remote) stdio bridge.

Once deployed behind real TLS (see [deploy](#deploying-to-kubernetes) below):

1. In Claude Desktop: **Settings → Connectors → Add custom connector**
2. URL: `https://<your-host>/mcp`
3. Advanced settings → set the bearer token you configured as the connector's auth header
   (`Authorization: Bearer <MCP_BEARER_TOKEN>`)

## Deploying to Kubernetes

The Helm chart in [`deploy/helm/vision-one-mcp`](deploy/helm/vision-one-mcp) is the single deployment artifact —
it's used identically whether you're hosting this yourself on EC2 or handing it to a customer running their own
cluster:

```bash
helm install vision-one-mcp deploy/helm/vision-one-mcp \
  --set secrets.visionOneApiKey=<your-api-key> \
  --set secrets.mcpBearerToken=<your-bearer-token> \
  --set config.visionOneRegion=us \
  --set ingress.host=vision-one-mcp.example.com
```

See [`deploy/helm/vision-one-mcp/README.md`](deploy/helm/vision-one-mcp/README.md) for the full values reference,
and [`deploy/ec2/README.md`](deploy/ec2/README.md) for standing up a k3s cluster on a fresh EC2 instance if you
don't already have a cluster to deploy into.

## Security notes

- Runs read-only by default and, in this v0.1 scope, *only* exposes read-only tools — there is no write/action
  path to Vision One in this codebase.
- The Vision One API key and the MCP bearer token are both secrets. They're injected via a Kubernetes `Secret`
  (see the Helm chart) — never commit real values into `values.yaml` or `.env`.
- This is a personal learning project, not an officially supported Trend Micro integration. For production use,
  prefer the [official Vision One MCP server](https://github.com/trendmicro/vision-one-mcp-server).

## License

MIT — see [LICENSE](LICENSE).
