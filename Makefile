.DEFAULT_GOAL := help
.PHONY: help doctor models up down port-forward replay benchmark test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-14s %s\n", $$1, $$2}'

doctor: ## Check required tools, Docker daemon, GPUs and Ollama
	@./scripts/doctor.sh

models: ## Pull the Ollama models listed in models.txt
	@./scripts/pull-models.sh

up: ## Create the kind cluster, install ArgoCD and apply the GitOps root app
	kind get clusters 2>/dev/null | grep -qx kubmedic || kind create cluster --config infra/kind/cluster.yaml
	kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.13.2/manifests/install.yaml
	kubectl -n argocd rollout status deployment/argocd-server --timeout=300s
	kubectl apply -f gitops/argocd/root-app.yaml
	@echo "ArgoCD is syncing the platform. UI: kubectl -n argocd port-forward svc/argocd-server 8080:443"

down: ## Delete the kind cluster
	kind delete cluster --name kubmedic

port-forward: ## Forward Prometheus (9090) and Loki (3100) for the agent/harness
	@echo "Prometheus http://127.0.0.1:9090 · Loki http://127.0.0.1:3100 (Ctrl-C stops both)"
	kubectl -n monitoring port-forward svc/monitoring-prometheus 9090:9090 & \
	kubectl -n monitoring port-forward svc/loki 3100:3100 & \
	wait

replay: ## Run the zero-cost replay eval gate (no cluster, no model calls)
	python3 -m evals.replay

benchmark: ## Run the live benchmark (needs the cluster; model via KUBMEDIC_MODEL)
	python3 -m evals.harness --model $${KUBMEDIC_MODEL:-ollama/qwen2.5:7b-instruct-q4_K_M}

test: ## Run the unit tests
	python3 -m pytest agent/tests evals/test_scoring.py -q
