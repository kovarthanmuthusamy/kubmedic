import pytest

from kubmedic_agent.tools.kubectl_tools import FakeKubectl, SubprocessKubectl


def test_fake_kubectl_rejects_write_verbs():
    backend = FakeKubectl({})
    with pytest.raises(PermissionError):
        backend.run(["delete", "pod", "x"])


def test_subprocess_kubectl_rejects_write_verbs_before_running():
    backend = SubprocessKubectl()
    with pytest.raises(PermissionError):
        backend.run(["apply", "-f", "x.yaml"])


def test_fake_kubectl_serves_canned_output():
    backend = FakeKubectl({"get pods": "pod-a 1/1 Running 0 1m"})
    assert "Running" in backend.run(["get", "pods", "-n", "boutique"])
