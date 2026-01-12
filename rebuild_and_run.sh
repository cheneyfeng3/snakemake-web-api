#!/bin/bash
set -e  # 遇到错误时退出

# 停止并删除旧容器
echo "停止容器 snakemake-web-api..."
docker stop snakemake-web-api || true

echo "删除容器 snakemake-web-api..."
docker rm snakemake-web-api || true

# 删除旧镜像（可选）
echo "删除旧镜像 snakemake-web-api:v1.0.2..."
docker rmi snakemake-web-api:v1.0.1 || true

# 构建新镜像
echo "构建新镜像 snakemake-web-api:v1.0.1..."
docker build -t snakemake-web-api:v1.0.2 .

# 启动容器，同时映射 8082 和 8083 端口
echo "启动容器 snakemake-web-api..."
docker run -d --name snakemake-web-api-v1.0.1 --restart always -p 8082:8082 -p 8083:8083 -v /mnt/juicefs/bdbe/snakemake:/mnt/juicefs/bdbe/snakemake:rw -v ~/.kube:/root/.kube:ro  snakemake-web-api:v1.0.1

echo "容器启动完成！可访问："
echo "REST API: http://localhost:8082"
echo "MCP 服务: http://localhost:8083"

docker run -d --name snakemake-mcp --restart always -p 8083:8083 -v /mnt/juicefs/bdbe/snakemake:/mnt/juicefs/bdbe/snakemake:rw -v ~/.kube:/root/.kube:ro snakemake-mcp:v1.0.0

docker run -d --name snakemake-web-api --restart always -p 8082:8082 -v /mnt/juicefs/bdbe/snakemake:/mnt/juicefs/bdbe/snakemake:rw -v ~/.kube:/root/.kube:ro ssnakemake-web-api:v1.0.0