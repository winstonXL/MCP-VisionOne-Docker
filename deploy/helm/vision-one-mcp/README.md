# vision-one-mcp Helm chart

Deploys `vision-one-mcp-python` to any Kubernetes cluster — a self-managed k3s cluster
on an AWS EC2 instance (see [../ec2](../ec2)) or a customer's own cluster (k3s, kubeadm,
EKS, OpenShift, etc.). Same chart, same image, no AWS-specific dependency anywhere in
the templates.

## Before installing

Build and push the image somewhere the cluster can pull it from (a private customer
cluster obviously can't pull from an image registry only *you* have access to):

```bash
docker build -t <your-registry>/vision-one-mcp-python:0.1.0 .
docker push <your-registry>/vision-one-mcp-python:0.1.0
```

Generate a bearer token if you don't already have one:

```bash
openssl rand -hex 32
```

## Install

Sanity-check the rendered manifests first:

```bash
helm lint deploy/helm/vision-one-mcp
helm template vision-one-mcp deploy/helm/vision-one-mcp \
  --set image.repository=<your-registry>/vision-one-mcp-python \
  --set secrets.visionOneApiKey=placeholder \
  --set secrets.mcpBearerToken=placeholder
```

Then install:

```bash
helm install vision-one-mcp deploy/helm/vision-one-mcp \
  --set image.repository=<your-registry>/vision-one-mcp-python \
  --set image.tag=0.1.0 \
  --set config.visionOneRegion=us \
  --set ingress.host=vision-one-mcp.example.com \
  --set secrets.visionOneApiKey=<vision-one-api-key> \
  --set secrets.mcpBearerToken=<bearer-token>
```

Passing secrets via `--set` puts them in `helm history` (base64-decoded, anyone with
`helm get values` access can see them). For anything beyond a personal single-user
deployment, create the Secret out of band and reference it instead:

```bash
kubectl create secret generic vision-one-mcp-secret \
  --from-literal=VISION_ONE_API_KEY=<vision-one-api-key> \
  --from-literal=MCP_BEARER_TOKEN=<bearer-token>

helm install vision-one-mcp deploy/helm/vision-one-mcp \
  --set secrets.existingSecretName=vision-one-mcp-secret \
  ...
```

## Values reference

| Key | Default | Description |
| --- | --- | --- |
| `replicaCount` | `2` | Pod replicas |
| `image.repository` | `ghcr.io/wphillips/vision-one-mcp-python` | Set to wherever you actually pushed the image |
| `image.tag` | `0.1.0` | Image tag |
| `config.visionOneRegion` | `us` | One of `us`, `eu`, `au`, `jp`, `sg`, `in`, `mea` |
| `config.visionOneBaseUrl` | `""` | Overrides the region mapping (internal/gov endpoints) |
| `secrets.visionOneApiKey` | `""` | Vision One API key (required unless `existingSecretName` set) |
| `secrets.mcpBearerToken` | `""` | Shared secret Claude Desktop authenticates with (required unless `existingSecretName` set) |
| `secrets.existingSecretName` | `""` | Use a pre-created Secret instead of templating one from the above |
| `ingress.enabled` | `true` | Set `false` to skip Ingress (e.g. cluster-internal only, fronted by something else) |
| `ingress.className` | `nginx` | Ingress controller class |
| `ingress.host` | `vision-one-mcp.example.com` | Public hostname |
| `ingress.annotations` | cert-manager example | Adjust for your ingress controller / cert issuer |
| `ingress.tls.enabled` | `true` | Terminate TLS at the ingress |
| `resources` | 100m/128Mi requests, 500m/256Mi limits | Tune for your cluster |

## Fully internal / air-gapped deployments

Claude Desktop's remote MCP custom connector validates the server's TLS certificate
like any HTTPS client — a self-signed cert will not work unless you've separately
distributed and trusted that CA on the machine running Claude Desktop, which isn't
practical for most customers. If a customer's cluster has no public DNS and no path to
a public CA (cert-manager + Let's Encrypt/ZeroSSL), realistic options are:

1. Terminate TLS at a reverse proxy/load balancer the customer already operates and
   already has a trusted cert for, forwarding to this service internally.
2. Use a private CA the customer's fleet already trusts, and install that CA on the
   machine(s) running Claude Desktop.
3. Skip the "hosted, always-on" model for that customer and use the official
   [vision-one-mcp-server](https://github.com/trendmicro/vision-one-mcp-server) locally
   over stdio instead — no network exposure required at all.

This chart doesn't attempt to solve TLS distribution for you; `ingress.tls` assumes
you have *some* valid cert path already, since that part is inherently
environment-specific.
