# KubeMedic platform, as Terraform — VALIDATED IN CI ONLY.
#
# The day-to-day install path is `make up` (kind + kubectl + the ArgoCD
# app-of-apps). This module expresses the same platform declaratively
# to demonstrate the IaC skill without needing a cloud account: CI runs
# `terraform init -backend=false`, `terraform validate` and
# `terraform fmt -check`; nothing here is applied by automation.

resource "kubernetes_namespace" "platform" {
  for_each = toset(["argocd", "boutique", "boutique-agent", "monitoring", "kyverno", "chaos-testing"])
  metadata {
    name = each.value
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      project                        = "kubmedic"
    }
  }
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  version    = var.argocd_chart_version
  namespace  = kubernetes_namespace.platform["argocd"].metadata[0].name

  set {
    name  = "server.extraArgs"
    value = "{--insecure}"
  }
}

# After ArgoCD is up, the GitOps root app (gitops/argocd/root-app.yaml)
# takes over; applying it is a `kubectl apply` in `make up`, kept out of
# Terraform so the GitOps flow stays the single control plane.
