"""KubeMedic agent: triage -> investigate -> plan -> pull request.

The agent is read-only against the cluster. Its only write path is a
pull request against the GitOps repo, which a human reviews and merges;
ArgoCD then deploys the fix. Safety lives in that architecture, not in
the prompt.
"""

__version__ = "0.1.0"
