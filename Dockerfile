# 基础镜像：Python 3.12（项目要求3.12+）
FROM docker.1ms.run/python:3.12-slim

# 安装系统依赖（git/conda依赖/基础工具）
RUN apt-get update && apt-get install -y \
    git \
    curl \
    bzip2 \
    vim \
    rsync \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装miniconda（适配Snakemake的conda环境管理）
RUN curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh && \
    bash miniconda.sh -b -p /opt/conda && \
    rm miniconda.sh && \
    /opt/conda/bin/conda clean -afy && \
    ln -s /opt/conda/bin/conda /usr/local/bin/conda && \
    # 核心新增：接受Conda渠道服务条款（解决tos报错）
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    # 可选：设置conda通道优先级（避免snakemake提示警告）
    conda config --set channel_priority strict

# 设置工作目录
WORKDIR /app

# 先安装uv包管理器（项目要求），提前安装避免后续依赖问题
RUN pip install uv build

# 复制项目核心文件（先复制pyproject.toml，保证依赖解析基础）
COPY pyproject.toml ./

# 复制整个项目文件（包括repos目录），确保插件源码完整
COPY . .

# 同步项目依赖（基于pyproject.toml，包含刚安装的插件依赖）
RUN uv sync --no-dev


# 初始化snakebase目录（克隆wrappers/workflows，项目核心依赖）
RUN mkdir -p /root/snakebase && \
    # 关键：创建软链接，指向/app/repos下的文件（仅存一份）
    ln -s /app/repos/snakemake-wrappers /root/snakebase/snakemake-wrappers && \
    ln -s /app/repos/snakemake-workflows /root/snakebase/snakemake-workflows && \
    cp -f /app/repos/snakemake-executor-plugin-kubernetes-main/snakemake_executor_plugin_kubernetes/__init__.py /app/.venv/lib/python3.12/site-packages/snakemake_executor_plugin_kubernetes/__init__.py && \
    # 确保软链接权限正确（继承源文件权限）
    chmod -R 755 /app/repos && \
    # 验证软链接有效性（可选，用于构建时排查）
    ls -l /root/snakebase/    

# 环境变量配置（项目核心）
ENV SNAKEBASE_DIR=/root/snakebase \
    SHARED_ROOT=/mnt/juicefs/bdbe/snakemake \
    SNAKEMAKE_CONDA_PREFIX=/root/.snakemake/conda \
    SNAKEMAKE_KUBERNETES_NAMESPACE=snakemake \
    SNAKEMAKE_KUBERNETES_SERVICE_ACCOUNT=snakemake-executor \
    SNAKEMAKE_KUBERNETES_PERSISTENT_VOLUME_CLAIM=snakemake-workspace \
    SNAKEMAKE_KUBERNETES_PVC_MOUNT_PATH=/mnt/juicefs/bdbe/snakemake \
    SNAKEMAKE_KUBERNETES_IMAGE=docker.1ms.run/snakemake/snakemake:latest \
    SNAKEMAKE_MAX_JOBS=10 \
    # SUPABASE_URL="http://10.3.200.31:8000" \
    # SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJzZXJ2aWNlX3JvbGUiLAogICAgImlzcyI6ICJzdXBhYmFzZS1kZW1vIiwKICAgICJpYXQiOiAxNjQxNzY5MjAwLAogICAgImV4cCI6IDE3OTk1MzU2MDAKfQ.DaYlNEoUrrEn2Ig7tqibS-PHK5vgusbcbo7X36XVt4Q" \
    # SUPABASE_TABLE_NAME=sciagi_mcp_snakemake_logger \
    LOG_LEVEL=INFO \
    PATH="/opt/conda/bin:/app/.venv/bin:$PATH"


# 单独安装supabase logger插件（确保正确安装到虚拟环境中）
RUN uv pip install -e /app/repos/snakemake-logger-plugin-supabase-main
# RUN pip install -e /app/repos/snakemake-logger-plugin-supabase-main


# 暴露API端口
EXPOSE 8082

# 启动命令（先解析wrappers，再启动REST API）
CMD ["sh", "-c", "uv run swa parse && uv run swa rest --host 0.0.0.0 --port 8082"]
