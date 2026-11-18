variable "kubeconfig_path" {
  type        = string
  default     = "~/.kube/config"
  description = "Path to the kubeconfig of the target (kind) cluster."
}

variable "argocd_chart_version" {
  type        = string
  default     = "7.7.0"
  description = "ArgoCD Helm chart version (argo-cd chart)."
}
