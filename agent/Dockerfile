FROM python:3.12-slim

# kubectl (read-only usage enforced in code and by RBAC) and git for the
# GitOps history tool and the PR writer.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git curl ca-certificates \
 && curl -fsSL -o /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl" \
 && chmod +x /usr/local/bin/kubectl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml ./
COPY kubmedic_agent ./kubmedic_agent
RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["uvicorn", "kubmedic_agent.webhook:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
