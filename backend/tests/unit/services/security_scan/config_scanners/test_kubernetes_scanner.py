"""Kubernetes scanner tests (Story 4.5)."""

from app.services.security_scan.config_scanners.kubernetes_scanner import (
    KubernetesScanner,
)

scanner = KubernetesScanner()


def _rules(content, filename="deployment.yaml"):
    return {f.rule_id for f in scanner.scan(content, filename)}


_HARDENED = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  namespace: production
spec:
  template:
    spec:
      containers:
        - name: web
          image: web:1.0
          securityContext:
            runAsNonRoot: true
          resources:
            limits:
              cpu: "500m"
              memory: "256Mi"
            requests:
              cpu: "250m"
              memory: "128Mi"
"""


def test_hardened_manifest_is_clean():
    assert _rules(_HARDENED) == set()


def test_privileged_container_detected():
    manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: p
  namespace: production
spec:
  containers:
    - name: c
      image: x:1
      securityContext:
        privileged: true
        runAsNonRoot: true
      resources:
        limits: {cpu: "1"}
        requests: {cpu: "1"}
"""
    assert "PRIVILEGED_CONTAINER" in _rules(manifest)


def test_default_namespace_detected():
    manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  template:
    spec:
      containers:
        - name: web
          image: web:1
          securityContext: {runAsNonRoot: true}
          resources:
            limits: {cpu: "1"}
            requests: {cpu: "1"}
"""
    assert "DEFAULT_NAMESPACE" in _rules(manifest)


def test_missing_resource_limits():
    manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: p
  namespace: prod
spec:
  containers:
    - name: c
      image: x:1
      securityContext: {runAsNonRoot: true}
"""
    assert "NO_RESOURCE_LIMITS" in _rules(manifest)


def test_run_as_root_when_no_security_context():
    manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: p
  namespace: prod
spec:
  containers:
    - name: c
      image: x:1
      resources:
        limits: {cpu: "1"}
        requests: {cpu: "1"}
"""
    assert "RUN_AS_ROOT" in _rules(manifest)


def test_host_network_detected():
    manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: p
  namespace: prod
spec:
  hostNetwork: true
  containers:
    - name: c
      image: x:1
      securityContext: {runAsNonRoot: true}
      resources:
        limits: {cpu: "1"}
        requests: {cpu: "1"}
"""
    assert "HOST_NETWORK" in _rules(manifest)


def test_non_workload_kind_ignored():
    manifest = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: cm\ndata:\n  k: v\n"
    assert _rules(manifest) == set()


def test_invalid_yaml_returns_empty():
    assert scanner.scan("kind: Pod\n  bad: : :", "x.yaml") == []
