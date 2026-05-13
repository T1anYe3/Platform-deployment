# 多组件 Docker 安全平台构建指南

> 基于 Platform 1 实战经验总结，适用于 Platform 2/3 及后续平台搭建。

---

## 目录

1. [项目结构规范](#1-项目结构规范)
2. [Docker Compose 模式](#2-docker-compose-模式)
3. [一键部署 init.sh 设计](#3-一键部署-initsh-设计)
4. [组件选型与集成](#4-组件选型与集成)
5. [TLS 证书体系](#5-tls-证书体系)
6. [数据管道（Bridge）模式](#6-数据管道bridge模式)
7. [健康检查设计](#7-健康检查设计)
8. [安全加固清单](#8-安全加固清单)
9. [常见陷阱与解决](#9-常见陷阱与解决)
10. [从 Platform 1 到 2/3 的模板化](#10-从-platform-1-到-23-的模板化)

---

## 1. 项目结构规范

```
platformN/
├── init.sh                  # 一键部署入口
├── docker-compose.yml       # 主编排文件
├── docker-compose.monitoring.yml  # 可选监控栈
├── Dockerfile.bridge        # 数据桥接容器（如有）
├── .env                     # 环境变量（密码、端口、资源配置）
├── .env.example             # 模板（可提交 Git）
├── .gitignore               # 排除 .env、test-data、*.sock
├── README.md                # 快速上手 + 完整文档
├── PROJECT-REPORT.md        # 项目交付报告
├── config/
│   ├── component-a/         # 每个组件独立目录
│   │   ├── config.yml
│   │   └── policies/
│   ├── prometheus/
│   │   ├── prometheus.yml
│   │   ├── alert.rules.yml
│   │   └── alertmanager.yml
│   └── grafana/
│       ├── datasources/
│       ├── dashboards/
│       └── dashboards-json/
├── scripts/
│   ├── init-certs.sh        # 证书生成
│   ├── init-<component>.sh  # 每个组件一个初始化脚本
│   ├── bridge_common.py     # 共享 Python 模块
│   ├── bridge-<source>.py   # 每个数据源一个桥接
│   ├── bridge-runner.py     # 桥接调度器
│   ├── health-check.sh      # 功能级健康检查
│   ├── backup.sh            # 备份脚本
│   └── restore.sh           # 恢复脚本
└── sample-data/             # 演示数据
```

**关键原则**：
- 每个组件的配置独立目录，互不干扰
- 所有脚本放 `scripts/`，不散落根目录
- `.env` 不提交 Git，`.env.example` 提交
- init.sh 在根目录，README 开头就要给出完整的一键命令

---

## 2. Docker Compose 模式

### 2.1 服务定义模板

```yaml
services:
  my-service:
    image: vendor/image:version          # 固定版本，不用 latest
    container_name: platformN-my-service  # 统一前缀 platformN-
    ports:
      - "${BIND_ADDRESS:-127.0.0.1}:PORT:PORT"  # 可配置绑定地址
    environment:
      - KEY=${ENV_VAR:-default}
    volumes:
      - ./config/my-service:/etc/config:ro     # 配置只读挂载
      - my-service-data:/var/lib/data          # 数据卷
    mem_limit: 512m                            # 内存上限
    logging:                                   # 日志轮转
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:PORT/health || exit 1"]
      interval: 30s
      retries: 5
      start_period: 30s       # 给慢启动组件更长时间
    restart: unless-stopped
    networks:
      - platformN
```

### 2.2 Init 容器模式

```yaml
  my-init:
    image: curlimages/curl:latest    # 或组件自带镜像
    volumes:
      - ./scripts:/scripts:ro
      - ./config:/config:ro
    environment:
      SERVICE_URL: http://my-service:PORT
    entrypoint: ["sh", "/scripts/init-my-service.sh"]
    depends_on:
      my-service:
        condition: service_healthy   # 等服务就绪再初始化
    networks:
      - platformN
```

### 2.3 关键经验

| 模式 | 说明 |
|------|------|
| `condition: service_healthy` | 避免竞态。init 容器等服务 healthy 后再运行 |
| `depends_on` + `condition` | compose v3.9+ 支持，等效于服务间启动顺序 |
| `network_mode: host` | 仅 Suricata/IDS 等需直接访问宿主机网卡的组件使用；Docker Desktop Windows 上行为受限 |
| 卷挂载 `:ro` | 配置全部只读，防止容器内误改写 |
| `container_name` 固定 | 用 `platformN-xxx` 命名，方便脚本中 `docker inspect` |
| 变量默认值 | 所有 `${VAR:-default}` 有默认值，确保不带 .env 也能启动 |

---

## 3. 一键部署 init.sh 设计

### 3.1 基本结构

```bash
#!/bin/bash
set -e
export MSYS_NO_PATHCONV=1   # Windows Git Bash 必需

# 参数解析 → 环境检查 → 证书生成 → 启动服务 → 等待 healthy
# → 运行 init 容器 → API 冒烟测试 → 打印访问地址
```

### 3.2 标志设计原则

```bash
bash init.sh                        # 最小部署（向后兼容）
bash init.sh --secure               # 安全模式（认证+密码生成）
bash init.sh --monitor              # 附加监控栈
bash init.sh --with-extra-component # 附加可选组件
bash init.sh --reset                # 清数据全新部署
bash init.sh --strict               # 严格模式（任一失败即中止）
bash init.sh --backup / --restore   # 备份恢复
```

**原则**：每个可选功能用独立标志，不互相绑定。用户可以自由组合。

### 3.3 密码生成

```bash
# 首次生成
if ! grep -q "^PASSWORD=" .env 2>/dev/null || $RESET; then
  PASSWORD=$(openssl rand -base64 24)
  echo "PASSWORD=${PASSWORD}" >> .env
fi
# 二次启动加载已有密码
export $(grep -E '^PASSWORD=' .env | xargs)
```

**关键**：`--secure` 启动后密码写入 `.env`；下次启动必须从 `.env` 加载到 shell 环境，否则 `docker compose` 拿到的 `${PASSWORD}` 为空。

### 3.4 等待服务就绪

```bash
SERVICES=(service-a service-b service-c)
MAX_WAIT=300
while [ $ELAPSED -lt $MAX_WAIT ]; do
  ALL_HEALTHY=true
  for svc in "${SERVICES[@]}"; do
    STATUS=$(docker inspect "platformN-${svc}" --format '{{.State.Health.Status}}' 2>/dev/null || echo "missing")
    [ "$STATUS" != "healthy" ] && ALL_HEALTHY=false && break
  done
  $ALL_HEALTHY && break
  sleep 5; ELAPSED=$((ELAPSED + 5))
done
```

### 3.5 错误处理

```bash
run_init() {
  local name="$1"
  local logfile="/tmp/init-${name}.log"
  if docker compose run --rm "${name}" >"${logfile}" 2>&1; then
    echo "  [OK] ${name}"
    rm -f "${logfile}"
  else
    echo "  [FAIL] ${name} (日志: ${logfile})"
    tail -3 "${logfile}"
    $STRICT_MODE && exit 1
  fi
}
```

---

## 4. 组件选型与集成

### 4.1 镜像选择

| 原则 | 说明 |
|------|------|
| 固定版本 | 永远不用 `:latest`，用 `:1.21` 或 `:9.4.0` |
| 官方优先 | Docker Hub 官方镜像 > 社区镜像 |
| 检查工具链 | 确认镜像内含必要工具（curl/wget/openssl/python） |
| 架构兼容 | Windows/Mac ARM 都有对应 tag |

### 4.2 组件间通信

```
组件 A（容器内）──► 组件 B（容器内）
                    通过 Docker 服务名：http://service-b:PORT
                    不通过 localhost（localhost 是容器自己）
```

```yaml
# Bridge 容器需要访问多个组件
environment:
  ES_URL: http://elasticsearch:9200        # 内网服务名
  VAULT_ADDR: https://vault:8200
  MINIO_URL: https://minio:9000
  NIFI_URL: https://nifi:8443
```

### 4.3 常见镜像问题速查

| 镜像 | 问题 | 解决 |
|------|------|------|
| `hashicorp/vault` | 不含 curl/wget | 用 `vault` 自带命令，或安装 wget |
| `hashicorp/vault` | CLI 强制 TTY | 用 HTTP API（wget POST）代替 CLI |
| `apache/nifi` | SNI 拒绝跨容器请求 | 设 `NIFI_WEB_PROXY_HOST` |
| `alpine:3.20` | 不含 openssl | `apk add openssl` |
| `curlimages/curl` | 不含 python | 需要 Python 时用 `python:3.12-alpine` |
| `jasonish/suricata` | 进程名 `Suricata-Main` | `pgrep -f Suricata-Main` |

---

## 5. TLS 证书体系

### 5.1 自签 CA 模式

```
Root CA (自签)
  ├── vault.key / vault.crt    → Vault TLS
  ├── nifi.key / nifi.crt      → NiFi TLS
  └── minio.key / minio.crt    → MinIO TLS
```

### 5.2 证书生成脚本

```bash
# 关键点：生成后 chmod a+r，否则非 root 容器无法读取
openssl genrsa -out root-ca.key 4096
openssl req -x509 -new -nodes -key root-ca.key -sha256 -days 3650 \
  -subj "/C=CN/O=PlatformN/CN=platformN-root-ca" -out root-ca.crt

for SVC in vault nifi minio; do
  openssl genrsa -out "${SVC}.key" 2048
  openssl req -new -key "${SVC}.key" \
    -subj "/CN=${SVC}.sec.local" -out "${SVC}.csr"
  # SAN 扩展：添加 DNS:localhost, DNS:${SVC}, IP:127.0.0.1
  openssl x509 -req -in "${SVC}.csr" -CA root-ca.crt -CAkey root-ca.key \
    -out "${SVC}.crt" -days 3650 -sha256 -extfile "${SVC}.ext"
done

chmod -R a+r /tls   # 关键：非 root 容器只读访问
```

### 5.3 TLS 挂载与验证

```yaml
volumes:
  - tls-data:/tls:ro   # 统一挂载到 /tls
```

- 容器内程序通过 `--cacert /tls/root-ca.crt` 或 `--certs-dir /tls` 加载
- 自签证书场景下，所有 curl 调用需 `-k` 或 `--cacert`
- bridge 脚本用 `ssl.CERT_NONE + check_hostname=False`

---

## 6. 数据管道（Bridge）模式

### 6.1 共享模块 bridge_common.py

```python
import os, json, base64, time, urllib.request, ssl, sys

ES_URL = os.environ.get('ELASTICSEARCH_URL', 'http://elasticsearch:9200')
ES_USER = os.environ.get('ELASTICSEARCH_USER', '')
ES_PASS = os.environ.get('ELASTICSEARCH_PASSWORD', '')

MAX_RETRIES = 3
RETRY_BACKOFF = [1, 3, 5]

def _retry_request(req, timeout, is_bulk=False):
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = urllib.request.urlopen(req, context=..., timeout=timeout)
            return json.loads(resp.read())
        except (URLError, OSError, ConnectionError) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF[attempt])
    raise last_error
```

### 6.2 桥接脚本模式

```python
from bridge_common import es_bulk_index, ensure_index_template, ES_URL

MAPPINGS = { ... }  # ES 字段映射

def main():
    ensure_index_template('my-index', MAPPINGS)
    data = fetch_from_source()    # 从组件 API/日志采集
    lines = build_bulk_body(data) # 构造 ES bulk 格式
    es_bulk_index(lines)
    print(f'Indexed {len(data)} records')
```

### 6.3 调度器 bridge-runner.py

```python
SCHEDULE = {
    'source-a': 60,    # 每 60 秒
    'source-b': 300,   # 每 5 分钟
    'source-c': 600,   # 每 10 分钟
}
# 循环：sleep(10) → 检查各 source 是否到时间 → 运行 bridge → 捕获异常继续
```

### 6.4 关键经验

- **状态管理**：每个 bridge 维护 `/state/<name>-bridge.json`（文件位置/事件ID），避免重复索引
- **重试**：ES 连接失败时自动重试（退避 1/3/5s）
- **日期分区**：ES 索引按 `name-YYYY.MM.DD` 命名，配合 ILM 自动过期
- **认证**：bridge_common 统一处理 ES Basic Auth，各 bridge 脚本不用重复

---

## 7. 健康检查设计

### 7.1 双层检查

| 层级 | 实现 | 用途 |
|------|------|------|
| Docker healthcheck | compose 中的 `healthcheck:` 指令 | Docker 自动重启 unhealthy 容器 |
| 功能级检查 | `health-check.sh` | 部署后人工/脚本验证 |

### 7.2 Docker healthcheck 关键点

```yaml
healthcheck:
  test: ["CMD-SHELL", "..." ]   # 用 CMD-SHELL 支持管道和条件
  interval: 30s
  retries: 5                    # 连续失败 N 次才标记 unhealthy
  start_period: 120s            # 慢启动组件给 2-3 分钟缓冲
```

**常见错误**：
- 镜像不含 curl → 用组件自带命令替代
- Docker Compose 变量插值吃掉 `$?` → 用 `$$?` 转义
- 命令返回非零但服务正常（如 Vault sealed 返回 2）→ 用 `|| [ $$? -eq 2 ]` 接受

### 7.3 功能级健康检查

```bash
check() {
  local label="$1" url="$2" expected_pattern="$3"
  code=$(curl -sk -o /tmp/hc.txt -w '%{http_code}' --connect-timeout 5 "$url")
  if [ "$code" = "200" ]; then
    grep -q "$expected_pattern" /tmp/hc.txt && UP=$((UP+1)) || DOWN=$((DOWN+1))
  fi
}
```

不仅检查端口可达，还检查返回内容是否符合预期（如 ES 返回 `cluster_name`、Vault 返回 `initialized`）。

---

## 8. 安全加固清单

部署到生产前逐项确认：

| # | 项目 | 实现 |
|---|------|------|
| 1 | ES 认证 | `xpack.security.enabled=true` + 随机密码 |
| 2 | Kibana 认证 | `elasticsearch.username/password` 传递 |
| 3 | TLS 全覆盖 | Vault/NiFi/MinIO 全部 TLS（自签或正式 CA） |
| 4 | 密码随机生成 | `openssl rand -base64 24` 写入 `.env` |
| 5 | 无硬编码密码 | 所有脚本用 `os.environ['PASSWORD']`（无默认值） |
| 6 | 端口绑定 | `BIND_ADDRESS=127.0.0.1`（默认仅本机） |
| 7 | 日志轮转 | json-file 50MB/5文件 |
| 8 | 资源限制 | `mem_limit` + `cpus` 防止 OOM |
| 9 | 配置只读 | 所有 config 挂载 `:ro` |
| 10 | 无 docker.sock | 健康检查用 curl 而非 docker.sock |
| 11 | .env 不入 Git | `.gitignore` 包含 `.env` |

---

## 9. 常见陷阱与解决

### 9.1 YAML 缩进错误

```yaml
# 错误：volumes 与 image 同级
my-service:
  image: xxx
volumes:          # 缩进不对！

# 正确：
my-service:
  image: xxx
  volumes:        # 缩进 2 格
```

**检查**：`docker compose config` 能快速发现 YAML 语法错误。

### 9.2 Docker Compose 变量插值

```bash
# 错误：$rc 被 Compose 当作 ${rc} 插值
test: ["CMD-SHELL", "cmd; rc=$?; [ $rc -eq 0 ]"]

# 正确：用 $$ 转义
test: ["CMD-SHELL", "cmd || [ $$? -eq 2 ]"]
```

### 9.3 Windows Git Bash 路径转换

```bash
# Git Bash 会自动把 /scripts/xxx 转换为 C:/Program Files/Git/scripts/xxx
# 解决：
export MSYS_NO_PATHCONV=1
```

### 9.4 镜像不含预期工具

| 镜像 | 缺失 | 替代 |
|------|------|------|
| `hashicorp/vault` | curl | `wget`（POST 数据）或 `vault` 自带命令 |
| `alpine` | openssl | `apk add --no-cache openssl` |
| `curlimages/curl` | python3 | 换 `python:3.12-alpine` |

### 9.5 健康检查循环依赖

```yaml
# 错误：vault-init 等 vault healthy；vault healthy 要求已初始化
# 解决：healthcheck 接受"sealed 但运行中"状态
test: ["CMD-SHELL", "vault status || [ $$? -eq 2 ]"]
```

### 9.6 容器间 TLS SNI 不匹配

```yaml
# NiFi 拒绝来自 "nifi:8443" 的请求（SNI 不匹配容器 hostname）
# 解决：
NIFI_WEB_PROXY_HOST: nifi:8443
```

### 9.7 数据卷权限

```bash
# Vault 数据卷新创建时 owner 为 root，vault 用户无法写入
# 解决：entrypoint 先 chown 再 exec 原始入口
entrypoint: ["/bin/sh", "-c", "chown -R vault:vault /vault/data; exec docker-entrypoint.sh ..."]
```

---

## 10. 从 Platform 1 到 2/3 的模板化

### 10.1 可复用的文件（直接拷贝）

```
scripts/bridge_common.py          ← ES 认证+重试+模板
scripts/init-certs.sh             ← TLS Root CA + 服务证书
scripts/health-check.sh           ← 功能级多服务检查
scripts/backup.sh / restore.sh   ← ES snapshot + 卷备份
docker-compose.monitoring.yml     ← Prometheus + Grafana + AlertManager
config/prometheus/                ← 告警规则 + 配置
config/grafana/                   ← 数据源 + Dashboard
.env.example                      ← 模板
.gitignore                        ← 完整忽略列表
```

### 10.2 需要改写的文件

| 文件 | 改写内容 |
|------|---------|
| `docker-compose.yml` | 替换组件列表（保留结构模式） |
| `init.sh` | 修改 `SERVICES` 数组、init 容器序列 |
| `scripts/bridge-*.py` | 修改 `MAPPINGS`、数据源 API 地址 |
| `scripts/bridge-runner.py` | 修改 `SCHEDULE` 字典 |
| `scripts/init-*.sh` | 修改组件特定的初始化逻辑 |
| `README.md` | 更新访问地址、凭证、参数表 |

### 10.3 快速启动新平台

```bash
# 1. 拷贝模板
cp -r platform1 platform2
cd platform2

# 2. 清理 Platform 1 特定内容
rm -rf safeline/ sample-data/ test-data/
rm scripts/bridge-safeline.py scripts/init-kibana.sh scripts/init-dashboards.py

# 3. 修改 docker-compose.yml
#    - 替换 services 列表
#    - 更新 SERVICE_NAMES 数组（init.sh 依赖）

# 4. 修改 init.sh
#    - 更新头部注释
#    - 更新 SERVICES 数组
#    - 更新 run_init 序列

# 5. 为新组件编写 init-*.sh 和 bridge-*.py

# 6. 测试
bash init.sh
```

---

## 附录：Platform 1 最终成果数据

| 指标 | 数值 |
|------|------|
| 核心服务 | 7 个（Vault + ES + Kibana + MinIO + NiFi + Suricata + Bridge） |
| 可选服务 | 10 个（SafeLine 7容器 + Prometheus + Grafana + AlertManager） |
| 容器总数（全功能） | 17 个 |
| Docker Compose 文件 | 2 个（主 + monitoring） |
| init.sh 参数 | 9 个 |
| 新增/修改文件 | 35+ 个 |
| KPI 通过率 | 6/6 PASS（Excellent） |
| 部署命令 | `bash init.sh --secure --monitor --with-safeline` |
| GitHub 仓库 | https://github.com/T1anYe3/Platform-deployment |
