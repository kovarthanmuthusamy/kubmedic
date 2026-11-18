from kubmedic_agent.tools.git_tools import parse_values_diff

DIFF = """diff --git a/gitops/app/values.yaml b/gitops/app/values.yaml
--- a/gitops/app/values.yaml
+++ b/gitops/app/values.yaml
@@ -20,9 +20,9 @@ services:
   checkoutservice:
     image: gcr.io/example/checkoutservice
     tag: v0.10.1
-    resources_limits_memory: 512Mi
+    resources_limits_memory: 64Mi
     resources_limits_cpu: 500m
   frontend:
     image: gcr.io/example/frontend
-    tag: v0.10.1
+    tag: v0.10.2
"""


def test_parse_values_diff_pairs_changes():
    changes = parse_values_diff(DIFF)
    by_key = {(c["service"], c["key"]): c for c in changes}
    assert by_key[("checkoutservice", "resources_limits_memory")]["before"] == "512Mi"
    assert by_key[("checkoutservice", "resources_limits_memory")]["after"] == "64Mi"
    assert by_key[("frontend", "tag")]["before"] == "v0.10.1"
    assert by_key[("frontend", "tag")]["after"] == "v0.10.2"


def test_parse_values_diff_empty():
    assert parse_values_diff("") == []
