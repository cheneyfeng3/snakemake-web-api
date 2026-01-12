#!/bin/bash
set -euo pipefail  # 增强错误处理：未定义变量/管道失败均退出

# ===================== 基础配置项 =====================
# Harbor仓库地址（可按需修改）
HARBOR_REGISTRY="10.3.200.26:5000"
# Harbor项目名（可按需修改）
HARBOR_PROJECT="mcptools"
# Harbor登录凭证（建议后续从环境变量读取，更安全）
HARBOR_USER="admin"
HARBOR_PWD="Mcp@2025"
# 脚本工作目录（镜像构建根目录）
WORK_DIR="/mnt/mcptools/images/code/snakemake-web-api/"

# ===================== 入参处理 =====================
# 用法提示函数
usage() {
    echo "用法: $0 [选项]"
    echo "选项说明："
    echo "  -n, --image-name    镜像名称（默认：snakemake-web-api）"
    echo "  -v, --version       镜像版本号（默认：v1.0.1）"
    echo "  -f, --dockerfile    Dockerfile路径（默认：.，即当前目录的Dockerfile）"
    echo "                      示例：-f ./Dockerfile.prod 或 -f /path/to/Dockerfile"
    echo "  -h, --help          显示帮助信息"
    exit 1
}

# 默认参数值
IMAGE_NAME="snakemake-web-api"
VERSION="v1.0.1"
DOCKERFILE_PATH="."  # 默认使用当前目录的Dockerfile

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--image-name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -f|--dockerfile)
            DOCKERFILE_PATH="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "错误：未知参数 $1"
            usage
            ;;
    esac
done

# 定义镜像标签（便于复用）
LOCAL_TAG="${IMAGE_NAME}:${VERSION}"
HARBOR_TAG="${HARBOR_REGISTRY}/${HARBOR_PROJECT}/${LOCAL_TAG}"
TAR_FILE="${IMAGE_NAME}_${VERSION}.tar"

# ===================== 辅助函数：删除镜像 =====================
delete_docker_image() {
    local tag="$1"
    # 检查镜像是否存在
    if docker images -q "$tag" > /dev/null 2>&1; then
        echo "删除已存在的镜像: $tag"
        # 强制删除镜像（-f），忽略依赖容器（避免因容器占用删不掉）
        docker rmi -f "$tag" || {
            echo "⚠️ 警告：镜像 $tag 删除失败（可能被容器占用），请手动清理"
            # 非致命错误，继续执行脚本
            return 1
        }
        echo "✅ 镜像 $tag 删除成功"
    else
        echo "ℹ️ 提示：镜像 $tag 不存在，无需删除"
    fi
}

# ===================== 核心逻辑 =====================
echo "===================== 前置清理 ====================="
# 1. 删除本地同名同版本镜像（避免构建冲突）
delete_docker_image "$LOCAL_TAG"
# 2. 删除本地Harbor标签的同名镜像（避免tag冲突）
delete_docker_image "$HARBOR_TAG"
# 3. 删除残留的tar包（避免重复构建时tar包覆盖失败）
if [[ -f "$TAR_FILE" ]]; then
    echo "删除残留的tar包: $TAR_FILE"
    rm -f "$TAR_FILE"
fi

echo "===================== 开始构建镜像 ====================="
echo "镜像名称: $IMAGE_NAME"
echo "版本号: $VERSION"
echo "Dockerfile路径: $DOCKERFILE_PATH"
echo "Harbor仓库: $HARBOR_TAG"

# 进入工作目录
echo "进入工作目录: $WORK_DIR"
cd "$WORK_DIR" || { echo "错误：无法进入目录 $WORK_DIR"; exit 1; }

# 构建Docker镜像（支持指定Dockerfile）
echo "开始构建镜像: $LOCAL_TAG"
if [[ "$DOCKERFILE_PATH" != "." ]]; then
    # 检查指定的Dockerfile是否存在
    if [[ ! -f "$DOCKERFILE_PATH" ]]; then
        echo "错误：指定的Dockerfile不存在 → $DOCKERFILE_PATH"
        exit 1
    fi
    docker build -f "$DOCKERFILE_PATH" -t "$LOCAL_TAG" .
else
    # 使用默认Dockerfile（当前目录）
    docker build -t "$LOCAL_TAG" .
fi

# 保存镜像为tar包
echo "保存镜像为tar包: $TAR_FILE"
docker save -o "$TAR_FILE" "$LOCAL_TAG"

# 登录Harbor
echo "登录Harbor仓库: $HARBOR_REGISTRY"
docker login "$HARBOR_REGISTRY" -u "$HARBOR_USER" -p "$HARBOR_PWD"

# 打Harbor标签
echo "为镜像打Harbor标签: $HARBOR_TAG"
docker tag "$LOCAL_TAG" "$HARBOR_TAG"

# 推送镜像到Harbor
echo "推送镜像到Harbor: $HARBOR_TAG"
docker push "$HARBOR_TAG"

# 登出Harbor（增强安全性）
echo "登出Harbor仓库"
docker logout "$HARBOR_REGISTRY"

# ===================== 清理临时文件 =====================
echo "删除临时tar包: $TAR_FILE"
if [[ -f "$TAR_FILE" ]]; then
    rm -f "$TAR_FILE"
    if [[ $? -eq 0 ]]; then
        echo "✅ tar包删除成功：$TAR_FILE"
    else
        echo "⚠️ 警告：tar包删除失败，请手动清理 → $TAR_FILE"
    fi
else
    echo "ℹ️ 提示：tar包不存在，无需删除"
fi

echo "===================== 操作完成 ====================="
echo "✅ 镜像构建并推送成功："
echo "   - 本地镜像: $LOCAL_TAG"
echo "   - Harbor镜像: $HARBOR_TAG"
echo "   - 已清理临时文件（tar包+旧镜像）"
echo "   - 使用的Dockerfile: $WORK_DIR/$DOCKERFILE_PATH"