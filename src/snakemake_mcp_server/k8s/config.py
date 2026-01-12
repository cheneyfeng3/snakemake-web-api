"""Kubernetes配置加载模块（支持相对路径）"""
import os
import sys
from pathlib import Path
from kubernetes import config
from kubernetes.client import Configuration
from typing import Optional, Union
from kubernetes.config.config_exception import ConfigException

def get_project_root() -> Path:
    """
    获取工程根目录（适配不同运行环境）
    逻辑：从当前文件向上找，直到找到 pyproject.toml 或 snakemake_mcp_server 目录
    """
    current_file = Path(__file__).resolve()
    # 向上遍历，找到工程根目录（src的上级目录）
    for parent in current_file.parents:
        # 判定条件：存在pyproject.toml 或 src目录（根据你的工程结构调整）
        if (parent / "pyproject.toml").exists() or (parent / "src").exists():
            return parent
    raise FileNotFoundError("无法识别工程根目录（未找到pyproject.toml或src目录）")

def load_kube_config(
    kubeconfig_path: Optional[Union[str, Path]] = None,
    use_relative: bool = True  # 是否优先使用工程内相对路径
) -> Configuration:
    """
    加载K8s配置，支持相对路径（工程根目录/configs/kubeconfig）
    :param kubeconfig_path: 自定义配置路径（绝对/相对）
    :param use_relative: 若为True，优先加载工程内 configs/kubeconfig
    :return: K8s客户端配置
    """
    # 1. 定义工程内默认配置路径（相对路径）
    project_root = get_project_root()
    default_relative_kubeconfig = project_root / "configs" / "kubeconfig"

    # 2. 确定最终加载的配置路径
    final_config_path: Optional[Path] = None
    if kubeconfig_path:
        # 若传入自定义路径：相对路径 → 转为工程根目录下的绝对路径；绝对路径 → 直接使用
        final_config_path = Path(kubeconfig_path)
        if not final_config_path.is_absolute():
            final_config_path = project_root / final_config_path
    elif use_relative and default_relative_kubeconfig.exists():
        # 优先使用工程内相对路径的配置
        final_config_path = default_relative_kubeconfig
    elif os.getenv("KUBECONFIG"):
        # 其次使用环境变量指定的路径
        final_config_path = Path(os.getenv("KUBECONFIG"))
    else:
        # 最后使用默认路径（~/.kube/config）
        final_config_path = Path.home() / ".kube" / "config"

    # 3. 验证配置文件存在
    if not final_config_path.exists():
        raise ConfigException(
            f"K8s配置文件不存在！路径：{final_config_path}\n"
            "请检查：\n"
            f"1. 工程内是否存在 {default_relative_kubeconfig}\n"
            "2. 环境变量 KUBECONFIG 是否配置\n"
            "3. 默认路径 ~/.kube/config 是否存在"
        )

    # 4. 加载配置
    try:
        config.load_kube_config(config_file=str(final_config_path))
        k8s_config = Configuration.get_default_copy()
        return k8s_config
    except Exception as e:
        raise RuntimeError(f"加载K8s配置失败！详情：{str(e)}") from e

def verify_k8s_connection() -> bool:
    """验证K8s集群连接是否正常"""
    from kubernetes.client import CoreV1Api
    try:
        load_kube_config()
        v1 = CoreV1Api()
        # 调用K8s API获取节点信息（验证连接）
        v1.list_node(limit=1)
        return True
    except Exception as e:
        print(f"❌ K8s集群连接失败：{str(e)}")
        return False

# 测试代码（可删除）
if __name__ == "__main__":
    # 测试加载相对路径配置
    try:
        load_kube_config()
        verify_k8s_connection()
    except Exception as e:
        print(f"测试失败：{e}")