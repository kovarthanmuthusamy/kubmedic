# Terraform (validate-only)

This module describes the KubeMedic platform namespaces and the ArgoCD
install declaratively. It is **validated in CI, never applied**: the
working install path is `make up`, and GitOps (ArgoCD) is the control
plane afterwards. The module exists to show the IaC skill honestly,
without pretending a local kind cluster needs a cloud apply pipeline.

CI runs: `terraform init -backend=false`, `terraform validate`,
`terraform fmt -check`.
