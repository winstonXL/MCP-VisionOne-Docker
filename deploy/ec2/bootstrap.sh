#!/usr/bin/env bash
# vision-one-mcp-python: bootstrap a single-node k3s cluster on a fresh Ubuntu box.
#
# Usable as EC2 user-data on launch, or by running it manually over SSH on any Ubuntu
# 22.04+ host -- cloud or on-prem. The k3s/Helm/cert-manager install steps here are not
# AWS-specific; this same script (minus the EC2-only IMDS lookup) is what you'd hand a
# customer to stand up their own cluster.
set -euo pipefail

K3S_VERSION="${K3S_VERSION:-v1.30.4+k3s1}"
HELM_VERSION="${HELM_VERSION:-v3.15.4}"
TARGET_USER="${SUDO_USER:-${USER}}"

log() { echo "[bootstrap] $*"; }

log "Installing k3s ${K3S_VERSION} (bundles containerd + Traefik ingress)..."
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="${K3S_VERSION}" sh -

log "Waiting for k3s to become ready..."
until sudo k3s kubectl get nodes >/dev/null 2>&1; do sleep 2; done

log "Wiring up kubeconfig for ${TARGET_USER}..."
TARGET_HOME=$(getent passwd "${TARGET_USER}" | cut -d: -f6)
mkdir -p "${TARGET_HOME}/.kube"
cp /etc/rancher/k3s/k3s.yaml "${TARGET_HOME}/.kube/config"
chown "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/.kube/config"
chmod 600 "${TARGET_HOME}/.kube/config"
export KUBECONFIG="${TARGET_HOME}/.kube/config"

log "Installing Helm ${HELM_VERSION}..."
curl -fsSL -o /tmp/get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod +x /tmp/get_helm.sh
INSTALL_HELM_VERSION="${HELM_VERSION}" bash /tmp/get_helm.sh

log "Installing cert-manager (for automatic Let's Encrypt certs)..."
sudo -u "${TARGET_USER}" env KUBECONFIG="${KUBECONFIG}" helm repo add jetstack https://charts.jetstack.io
sudo -u "${TARGET_USER}" env KUBECONFIG="${KUBECONFIG}" helm repo update
sudo -u "${TARGET_USER}" env KUBECONFIG="${KUBECONFIG}" helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set crds.enabled=true

log "Done."
log "k3s ships with Traefik as its default ingress controller. This chart's default"
log "values assume ingress-nginx (ingress.className=nginx) to match typical customer"
log "clusters -- either install ingress-nginx separately, or override with:"
log "  --set ingress.className=traefik"
log ""
log "Next steps:"
log "  1. Point DNS for your chosen hostname at this box's public/elastic IP."
log "  2. kubectl apply -f deploy/ec2/cluster-issuer.yaml  (edit the email first)"
log "  3. helm install vision-one-mcp deploy/helm/vision-one-mcp --set ... (see deploy/helm/vision-one-mcp/README.md)"
