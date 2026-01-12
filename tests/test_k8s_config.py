"""Test Kubernetes config loading"""
from src.snakemake_mcp_server.k8s.config import load_kube_config
import os
import pytest

def test_load_default_kubeconfig():
    if os.path.exists(os.path.expanduser("~/.kube/config")):
        config = load_kube_config()
        assert config.host is not None

def test_load_custom_kubeconfig():
    with open("test_kubeconfig", "w") as f:
        f.write("apiVersion: v1\nclusters: []\n")  # 最小有效配置
    config = load_kube_config("test_kubeconfig")
    assert config is not None