# Deploying on AWS EC2 (Docker + Caddy)

Runs `vision-one-mcp-python` as a container on a single EC2 instance, with
[Caddy](https://caddyserver.com/) in front handling HTTPS automatically (Let's Encrypt,
no manual certificate management). No Kubernetes, no AWS-managed services beyond the
instance itself — just Docker Compose.

## 1. Launch the instance

- AMI: Ubuntu 22.04 LTS
- Size: `t3.small` is plenty for this workload alone
- Storage: 20 GB gp3
- Allocate an Elastic IP so DNS doesn't break on instance stop/start

### Security group

| Port | Source | Purpose |
| --- | --- | --- |
| 22 | your IP only | SSH |
| 80 | 0.0.0.0/0 | HTTP — required for the ACME HTTP-01 challenge and redirect to HTTPS |
| 443 | 0.0.0.0/0 | HTTPS — the actual MCP endpoint Claude Desktop talks to |

Nothing else needs to be open. The app container never listens on a host port directly
(see `docker-compose.yml` — it uses `expose`, not `ports`); only Caddy is internet-facing.

## 2. Bootstrap Docker

SSH in and run [`bootstrap.sh`](bootstrap.sh) (or pass it as EC2 user-data at launch
time):

```bash
scp deploy/ec2/bootstrap.sh ubuntu@<instance-ip>:~/
ssh ubuntu@<instance-ip> 'chmod +x bootstrap.sh && sudo ./bootstrap.sh'
```

This installs Docker Engine and the Compose plugin. Nothing AWS-specific about it — the
same script works on a customer's on-prem Ubuntu box.

## 3. Point DNS

Create an A record for your chosen hostname (e.g. `vision-one-mcp.example.com`)
pointing at the instance's Elastic IP. Caddy needs this to resolve *before* it can
obtain a certificate.

## 4. Configure and deploy

```bash
git clone <your-repo-url> && cd vision-one-mcp-python
cp .env.example .env
# edit .env: VISION_ONE_API_KEY, MCP_BEARER_TOKEN, CADDY_DOMAIN, CADDY_EMAIL

docker compose up -d --build
docker compose logs -f caddy   # watch it obtain the certificate
```

## 5. Verify

```bash
curl https://vision-one-mcp.example.com/healthz
# {"status": "ok"}
```

Then add it to Claude Desktop as a custom connector pointing at
`https://vision-one-mcp.example.com/mcp` with the bearer token as the auth header (see
the root [README](../../README.md#connecting-claude-desktop)).

## Replicating this for customers

There's no AWS dependency in `docker-compose.yml`, the `Dockerfile`, or the `Caddyfile`
— a customer with any Linux box (or Mac/Windows with Docker Desktop, for testing) and
their own domain can run the exact same three commands from step 4. What differs per
customer is just their own Vision One API key, bearer token, and domain/DNS — handed to
them as their own `.env`, nothing else needs to change.

If a customer has no public DNS at all (fully internal deployment), Caddy's automatic
Let's Encrypt flow won't work, since Claude Desktop's remote MCP connector requires a
publicly-trusted certificate. In that case terminate TLS at whatever reverse proxy /
load balancer they already operate and already have a trusted cert for, and point it at
this container's `expose`d port instead of using the bundled Caddy service.
