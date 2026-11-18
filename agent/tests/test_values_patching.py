import pytest
import yaml

from kubmedic_agent.patching import build_fix_diff
from kubmedic_agent.values import apply_edits, load_values

VALUES = {
    "services": {
        "checkoutservice": {
            "image": "gcr.io/example/checkoutservice",
            "tag": "v0.10.1",
            "resources_limits_memory": "512Mi",
        }
    }
}


def _write_gitops(tmp_path):
    path = tmp_path / "gitops" / "app"
    path.mkdir(parents=True)
    (path / "values.yaml").write_text(yaml.safe_dump(VALUES, sort_keys=False))
    return tmp_path


def test_apply_edits_changes_only_the_target_key():
    new = apply_edits(
        VALUES,
        [{"service": "checkoutservice", "key": "resources_limits_memory", "value": "1Gi"}],
    )
    assert new["services"]["checkoutservice"]["resources_limits_memory"] == "1Gi"
    assert VALUES["services"]["checkoutservice"]["resources_limits_memory"] == "512Mi"


def test_apply_edits_rejects_unknown_key():
    with pytest.raises(KeyError):
        apply_edits(VALUES, [{"service": "checkoutservice", "key": "nope", "value": 1}])


def test_apply_edits_rejects_unknown_service():
    with pytest.raises(KeyError):
        apply_edits(VALUES, [{"service": "nope", "key": "tag", "value": "v1"}])


def test_build_fix_diff(tmp_path):
    root = _write_gitops(tmp_path)
    assert load_values(root) == VALUES
    diff, _new = build_fix_diff(
        root, [{"service": "checkoutservice", "key": "resources_limits_memory", "value": "1Gi"}]
    )
    assert "-        resources_limits_memory: 512Mi" in diff or "512Mi" in diff
    assert "1Gi" in diff
