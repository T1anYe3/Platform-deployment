#!/bin/bash
# ==========================================================================
# SafeLine CE (雷池 WAF) 独立部署脚本
# 与主 Platform 1 compose 共享同一个 Docker 网络，bridge 可互通
# 用法: bash safeline/deploy.sh [--reset]
# ==========================================================================

set -e
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
log()  { echo -e "${GREEN}[safeline]${NC} $1"; }
warn() { echo -e "${YELLOW}[safeline]${NC} $1"; }
err()  { echo -e "${RED}[safeline]${NC}  $1"; }

echo ""
echo "=============================================="
echo "  SafeLine CE (雷池 WAF) 部署"
echo "=============================================="
echo ""

# ---- Step 0: 检查 Docker ----
log "检查 Docker 环境..."
if ! docker info >/dev/null 2>&1; then
  err "Docker 未运行，请先启动 Docker Desktop。"
  exit 1
fi

# ---- Step 1: 检查/下载 compose ----
if [ ! -f "compose.yaml" ]; then
  log "下载 SafeLine CE compose.yaml..."
  curl -skL "https://waf-ce.chaitin.cn/release/latest/compose.yaml" -o compose.yaml
fi

# ---- Step 2: 配置 .env ----
if [ ! -f ".env" ]; then
  warn ".env 不存在，使用默认配置创建..."
  cat > .env << EOFENV
SAFELINE_DIR=${SCRIPT_DIR}
IMAGE_TAG=latest
MGT_PORT=9443
POSTGRES_PASSWORD=$(LC_ALL=C tr -dc A-Za-z0-9 </dev/urandom 2>/dev/null | head -c 32 || echo "Platform1SafeLine2026!")
SUBNET_PREFIX=172.22.223
IMAGE_PREFIX=swr.cn-east-3.myhuaweicloud.com/chaitin-safeline
ARCH_SUFFIX=
REGION=
MGT_PROXY=0
EOFENV
fi

# ---- Step 3: --reset 清理 ----
if [ "$1" = "--reset" ]; then
  warn "--reset: 清理 SafeLine 数据和容器..."
  docker compose -f compose.yaml down -v 2>/dev/null || true
fi

# ---- Step 4: 确保主网络存在 ----
PLATFORM_NETWORK="platform1-docker_platform1"
if ! docker network inspect "$PLATFORM_NETWORK" >/dev/null 2>&1; then
  warn "Platform 1 网络不存在，请先运行主 init.sh"
  warn "现在为你创建网络..."
  docker network create "$PLATFORM_NETWORK"
fi

# ---- Step 5: 启动 SafeLine ----
log "启动 SafeLine CE 容器..."
docker compose -f compose.yaml up -d

# ---- Step 6: 将 mgt 加入主网络 ----
log "将 safeline-mgt 接入 ${PLATFORM_NETWORK} 网络..."
if ! docker network inspect "$PLATFORM_NETWORK" | grep -q '"safeline-mgt"'; then
  docker network connect "$PLATFORM_NETWORK" safeline-mgt 2>/dev/null || \
    warn "safeline-mgt 尚未就绪，稍后重试..."
fi

# ---- Step 7: 等待服务就绪 ----
log "等待 SafeLine 核心服务就绪..."
MAX_WAIT=120
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
  if docker inspect safeline-mgt --format '{{.State.Health.Status}}' 2>/dev/null | grep -q 'healthy'; then
    log "SafeLine 管理服务已 healthy！"
    break
  fi
  sleep 5
  ELAPSED=$((ELAPSED + 5))
  echo -n "."
done
echo ""

# ---- Step 8: 初始化管理员 ----
log "初始化 SafeLine 管理员密码..."
docker exec safeline-mgt resetadmin 2>/dev/null || \
  warn "resetadmin 不可用，可能已初始化（请访问 https://localhost:9443 登录）"

# ---- 完成 ----
echo ""
echo "=============================================="
echo -e "  ${GREEN}SafeLine CE 部署完成！${NC}"
echo ""
echo "  管理控制台: https://localhost:9443"
echo "  用户名:     admin"
echo "  密码:       请查看上方 resetadmin 输出"
echo ""
echo "  Platform 1 bridge 将通过"
echo "  https://safeline-mgt:1443 访问 SafeLine API"
echo "=============================================="
