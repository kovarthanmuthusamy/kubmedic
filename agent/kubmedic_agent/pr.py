"""The agent's only write path: a branch + pull request in the GitOps
repo. It never writes to main, and it never touches the cluster.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from kubmedic_agent.values import VALUES_REL_PATH, dump_values

PROTECTED_BRANCHES = {"main", "master"}


def _git(repo: str, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", repo, *args], check=False, capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


class GitOpsWriter:
    def __init__(self, repo_path: str | Path, create_github_pr: bool = False):
        self.repo = str(repo_path)
        self.create_github_pr = create_github_pr

    def open_fix_pr(
        self,
        *,
        branch: str,
        new_values: dict,
        title: str,
        body: str,
    ) -> dict:
        if branch in PROTECTED_BRANCHES:
            raise ValueError("refusing to write to a protected branch")
        _git(self.repo, "checkout", "-B", branch)
        values_path = Path(self.repo) / VALUES_REL_PATH
        values_path.write_text(dump_values(new_values), encoding="utf-8")
        _git(self.repo, "add", str(VALUES_REL_PATH))
        _git(
            self.repo,
            "-c",
            "user.name=KubeMedic",
            "-c",
            "user.email=kubmedic@localhost",
            "commit",
            "-m",
            title,
        )
        commit = _git(self.repo, "rev-parse", "--short", "HEAD")
        pr_url = None
        if self.create_github_pr:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".md", delete=False, encoding="utf-8"
            ) as fh:
                fh.write(body)
                body_file = fh.name
            _git(self.repo, "push", "-u", "origin", branch)
            proc = subprocess.run(
                ["gh", "pr", "create", "--title", title, "--body-file", body_file],
                cwd=self.repo,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "gh pr create failed")
            pr_url = proc.stdout.strip()
        _git(self.repo, "checkout", "-")
        return {"branch": branch, "commit": commit, "pr_url": pr_url, "title": title}
