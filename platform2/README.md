# Platform 2 -- 数据全生命周期管理平台 Docker 部署指南

> **一键部署**：`bash init.sh --secure`

---

## 概述

Platform 2 是一个基于 Docker Compose 的数据全生命周期管理平台，集成了以下核心组件：

| 组件 | 镜像 | 用途 | 端口 |
|------|------|------|------|
| **Vault** | hashicorp/vault:1.21 | 密钥与凭证管理 | 8200 (HTTPS) |
| **Elasticsearch** | elasticsearch:9.4.0 | 日志存储与检索 | 9200 |
| **Kibana** | kibana:9.4.0 | 可视化与仪表板 | 5601 |
| **MinIO** | minio/minio:latest | 对象存储（6个数据桶） | 9000/9001 |
| **NiFi** | apache/nifi:2.3.0 | 数据流编排 | 8443 (HTTPS) |
| **Bridge** | python:3.12-alpine | 数据管道调度 | - |

### 数据全生命周期流程

```
数据采集 (CSV/JSON) -> NiFi 数据流编排 -> MinIO 对象存储 -> Bridge 桥接采集 -> Elasticsearch -> Kibana 可视化
```

---

## 快速开始

### 前提条件

- Docker Desktop (Windows/Mac) 或 Docker Engine (Linux)
- Docker Compose v2+
- 8GB+ 可用内存
- 20GB+ 可用磁盘

### 最小部署

```bash
cd platform2
bash init.sh
```

### 安全模式部署（推荐）

```bash
bash init.sh --secure
```

### 带监控栈部署

```bash
bash init.sh --secure --monitor
```

### 完全清理后重新部署

```bash
bash init.sh --reset --secure
```

---

## init.sh 参数说明

| 参数 | 说明 |
|------|------|
| `--reset` | 删除所有数据卷和容器，全新初始化 |
| `--skip-init` | 只启动服务，不运行初始化容器 |
| `--secure` | 启用 ES/Kibana 认证，自动生成随机密码 |
| `--monitor` | 附加部署 Prometheus + Grafana 监控栈 |
| `--backup` | 执行数据备份 |
| `--restore PATH` | 从指定备份路径恢复数据 |
| `--strict` | 严格模式，任一 init 失败则中止部署 |
| `--help` | 显示帮助信息 |

---

## 访问地址

部署完成后，可通过以下地址访问各组件：

| 组件 | URL | 认证 |
|------|-----|------|
| Kibana | http://localhost:5601 | admin / (--secure 时随机生成) |
| MinIO Console | http://localhost:9001 | minioadmin / ChangeThis-Local-123! |
| Vault UI | https://localhost:8200 | root token (见 init 日志) |
| NiFi | https://localhost:8443/nifi | admin / Admin123!ChangeMe |
| Elasticsearch | http://localhost:9200 | elastic / (--secure 时随机生成) |

### Kibana 仪表板

| 仪表板 | URL |
|--------|-----|
| Data Lifecycle Overview | http://localhost:5601/app/dashboards#/view/platform2-data-lifecycle |
| MinIO Bucket Status | http://localhost:5601/app/dashboards#/view/platform2-minio-status |
| NiFi Flow Status | http://localhost:5601/app/dashboards#/view/platform2-nifi-status |

### 监控（使用 --monitor 时）

| 组件 | URL |
|------|-----|
| Prometheus | http://localhost:9090 |
| AlertManager | http://localhost:9093 |
| Grafana | http://localhost:3000 (admin/platform2) |

---

## 项目结构

```
platform2/
├── init.sh                    # 一键部署入口
├── docker-compose.yml         # 主编排文件
├── docker-compose.monitoring.yml  # 可选监控栈
├── Dockerfile                 # Bridge 容器构建文件
├── .env.example               # 环境变量模板
├── .gitignore                 # Git 忽略规则
├── README.md                  # 本文件
├── PROJECT-REPORT.md          # 项目交付报告
├── TEST-PLAN.md               # 测试方案
├── config/
│   ├── vault/                 # Vault 配置与策略
│   ├── elasticsearch/         # ES 配置
│   ├── kibana/               # Kibana 配置
│   ├── prometheus/           # Prometheus 配置与告警
│   └── grafana/              # Grafana 数据源与仪表板
└── scripts/
    ├── bridge_common.py       # 共享桥接模块
    ├── bridge-minio.py        # MinIO -> ES 桥接
    ├── bridge-nifi.py         # NiFi -> ES 桥接
    ├── bridge-vault.py        # Vault -> ES 桥接
    ├── bridge-runner.py       # 桥接调度器
    ├── init-certs.sh          # TLS 证书生成
    ├── init-vault.sh          # Vault 初始化
    ├── init-minio.sh          # MinIO 桶创建
    ├── init-kibana.sh         # Kibana 索引模式
    ├── init-nifi.sh           # NiFi 流模板
    ├── init-dashboards.py     # Kibana 仪表板创建
    ├── init-ilm.sh            # ES ILM 策略
    ├── init-es-users.sh       # ES 用户初始化
    ├── health-check.sh        # 功能健康检查
    ├── security-benchmark.py  # KPI 基准测试
    ├── run-full-benchmark.py  # 完整基准报告
    ├── generate-test-data.py  # 测试数据生成
    ├── backup.sh              # 数据备份
    └── restore.sh             # 数据恢复
```

---

## MinIO 数据桶

Platform 2 预配置了 6 个数据全生命周期桶：

| 桶名 | 用途 | 生命周期 |
|------|------|----------|
| `raw-data` | 原始采集数据 | 90 天 |
| `processed-data` | 已处理/转换数据 | 180 天 |
| `model-files` | ML 模型文件 | 365 天 |
| `evaluation-results` | 模型评估结果 | 180 天 |
| `archive-data` | 长期归档数据 | 730 天 |
| `audit-evidence` | 审计证据（不可变） | 受控保留 |

---

## 常用操作

### 查看服务状态

```bash
docker compose ps
```

### 查看服务日志

```bash
docker compose logs -f [service-name]
```

### 重启单个服务

```bash
docker compose restart [service-name]
```

### 完全停止并清理

```bash
docker compose down -v
```

### 运行健康检查

```bash
docker compose run --rm health-check
```

### 运行基准测试

```bash
# 生成测试数据
python3 scripts/generate-test-data.py

# 运行完整基准
python3 scripts/run-full-benchmark.py --full

# 或运行单个指标
python3 scripts/security-benchmark.py --metric tls
```

---

## 故障排除

| 问题 | 解决方案 |
|------|----------|
| Docker 未运行 | 启动 Docker Desktop 或 Docker Engine |
| 端口冲突 | 修改 `.env` 中的 `BIND_ADDRESS` 为其他 IP |
| 内存不足 | 减少 `ES_MEMORY` 值（默认 2g） |
| TLS 证书过期 | 运行 `docker compose down -v && bash init.sh --reset` |
| NiFi 启动超时 | 等待 3-5 分钟，NiFi 首次启动较慢 |
| Bridge 无法连接 | 确认 elasticsearch 和 vault 已 healthy |

---

## 凭证说明

- **部署密码**：使用 `--secure` 时自动生成并写入 `.env` 文件，请勿将 `.env` 提交到版本控制
- **默认密码**（仅适用于非 `--secure` 模式）：
  - MinIO: `minioadmin` / `ChangeThis-Local-123!`
  - NiFi: `admin` / `Admin123!ChangeMe`
  - Vault: 初始化时自动生成 root token
