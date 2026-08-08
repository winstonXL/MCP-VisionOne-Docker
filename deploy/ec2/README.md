# Deploying on AWS EC2 (single-node k3s)

This stands up a real Kubernetes cluster (k3s, not EKS) on a single EC2 instance, then
deploys the Helm chart from [`../helm/vision-one-mcp`](../helm/vision-one-mcp) onto it.
Nothing here is AWS-managed Kubernetes — that's deliberate: the exact same steps (minus
launching an EC2 instance) work on a customer's own on-prem box. See
["Replicating this for customers"](#replicating-this-for-customers) below.

## 1. Launch the instance

- AMI: Ubuntu 22.04 LTS
- Size: `t3.medium` or larger (k3s + cert-manager + this server comfortably fits in
  2 vCPU / 4 GB RAM; go bigger if you'll run other workloads on the same box)
- Storage: 20 GB gp3 is plenty to start
- Allocate an Elastic IP so DNS doesn't break on instance stop/start

### Security group

| Port | Source | Purpose |
| --- | --- | --- |
| 22 | your IP only | SSH |
| 80 | 0.0.0.0/0 | HTTP — required for the ACME HTTP-01 challenge (Let's Encrypt) and redirect to HTTPS |
| 443 | 0.0.0.0/0 | HTTPS — this is the actual MCP endpoint Claude Desktop talks to |
| 6443 | your IP only (or omit entirely) | k3s API server — only needed if you want `kubectl` from your laptop instead of SSHing in |

Don't expose 6443 to `0.0.0.0/0`. There's no reason for the Kubernetes API itself to be
internet-reachable; everything you need (the MCP server) is served through 443 via the
Ingress.

## 2. Bootstrap the cluster

SSH in and run [`bootstrap.sh`](bootstrap.sh) (or pass it as EC2 user-data at launch
time and skip the manual SSH step):

```bash
scp deploy/ec2/bootstrap.sh ubuntu@<instance-ip>:~/
ssh ubuntu@<instance-ip> 'chmod +x bootstrap.sh && ./bootstrap.sh'
```

This installs k3s, wires up `kubeconfig`, installs Helm, and installs cert-manager.

## 3. Point DNS and issue a certificate

1. Create an A record for your chosen hostname (e.g. `vision-one-mcp.example.com`)
   pointing at the instance's Elastic IP.
2. Edit the email in [`cluster-issuer.yaml`](cluster-issuer.yaml), then:
   ```bash
   kubectl apply -f deploy/ec2/cluster-issuer.yaml
   ```

k3s ships with Traefik as its built-in ingress controller. This chart's default values
assume `ingress-nginx` (`ingress.className: nginx`) since that's more likely to match a
customer's existing cluster — either install ingress-nginx on this box too, or just
override the value:

```bash
helm install ingress-nginx ingress-nginx \
  --repo https://kubernetes.github.io/ingress-nginx \
  --namespace ingress-nginx --create-namespace
```

or set `--set ingress.className=traefik` at install time to use what k3s already gives you.

## 4. Build and push the image

The cluster needs to pull the image from somewhere. Any registry works (ECR, GHCR,
Docker Hub):

```bash
docker build -t <your-registry>/vision-one-mcp-python:0.1.0 .
docker push <your-registry>/vision-one-mcp-python:0.1.0
```

## 5. Deploy

```bash
helm install vision-one-mcp deploy/helm/vision-one-mcp \
  --set image.repository=<your-registry>/vision-one-mcp-python \
  --set image.tag=0.1.0 \
  --set ingress.host=vision-one-mcp.example.com \
  --set secrets.visionOneApiKey=<your-vision-one-api-key> \
  --set secrets.mcpBearerToken=<your-bearer-token>
```

## 6. Verify

```bash
curl https://vision-one-mcp.example.com/healthz
# {"status": "ok"}
```

Then add it to Claude Desktop as a custom connector pointing at
`https://vision-one-mcp.example.com/mcp` with the bearer token as the auth header (see
the root [README](../../README.md#connecting-claude-desktop)).

## Replicating this for customers

The point of using plain k3s on a plain EC2 instance instead of EKS is that nothing
here depends on AWS being present at all:

- `curl -sfL https://get.k3s.io | sh -` is the same command on a customer's on-prem
  Ubuntu/RHEL box as it is on this EC2 instance.
- The Helm chart doesn't reference any AWS resource (no ALB, no EBS volumes, no IAM
  roles) — it's plain Kubernetes primitives (Deployment, Service, Ingress, Secret,
  ConfigMap), so it applies to k3s, kubeadm, EKS, or OpenShift-with-tweaks equally.
- What *does* change per customer: where the image is pulled from (their registry vs.
  yours), their ingress controller/DNS/cert setup, and obviously their own Vision One
  API key and bearer token.

In practice, handing this to a customer means: give them the Docker image (or a
Dockerfile + source so they can build it themselves inside their own network), the
Helm chart, and this README with the AWS-specific launch step removed. Everything from
"Bootstrap the cluster" onward is identical.
