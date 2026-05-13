# Platform 3 -- 合规与应急响应平台 Docker 部署指南

> **一键部署**：`bash init.sh --secure`

---

## 目录

1. [平台简介](#1-平台简介)
2. [快速开始](#2-快速开始)
3. [准备工作：安装 Docker](#3-准备工作安装-docker)
4. [部署选项说明](#4-部署选项说明)
5. [访问与演示](#5-访问与演示)
6. [日志采集](#6-日志采集)
7. [常用操作](#7-常用操作)
8. [故障排查](#8-故障排查)

---

## 1. 平台简介

Platform 3（合规与应急响应平台）是三平台架构中的**统一日志汇聚与可视化层**。它不运行自己的 MinIO、NiFi 或 Suricata，而是从 Platform 1 和 Platform 2 服务中采集日志，提供统一的检索、分析和态势展示能力。

### 核心组件

| 组件 | 用途 | 访问地址 |
|------|------|---------|
| Elasticsearch 9.4.0 | 统一日志后端，存储与检索 | http://localhost:19200 |
| Kibana 9.4.0 | 可视化仪表板与检索 | http://localhost:15601 |
| Vault 1.21 | 轻量级凭证管理 | https://localhost:18200 |
| Prometheus | 监控指标采集 | http://localhost:9090（--monitor） |
| Grafana | 监控可视化 | http://localhost:3000（--monitor） |

### 5 大日志数据源

| 数据源 | ES 索引 | 来源 | 采集脚本 |
|--------|---------|------|---------|
| SafeLine WAF 攻击记录 | safeline-records-* | Platform 1 | ingest-safeline.py |
| Suricata IDS 告警 | suricata-alerts-* | Platform 1 | ingest-suricata.py |
| Vault 审计日志 | vault-audit-* | 本地 Vault | ingest-vault-audit.py |
| MinIO 状态事件 | minio-audit-* | Platform 2 | ingest-minio-audit.py |
| NiFi 系统诊断 | nifi-logs-* | Platform 2 | ingest-nifi-logs.py |

### 关键特性

- **统一日志后端**：5 个数据源统一写入 Elasticsearch，按日期分片
- **标准化字段**：所有记录包含 `@timestamp` 和 `event.source` 字段
- **预置仪表板**：2 个 Dashboard + 5 个 Saved Search
- **ILM 策略**：30 天自动日志保留与清理
- **独立端口**：与 Platform 1 端口完全隔离（ES:19200, Kibana:15601, Vault:18200）

---

## 2. 快速开始

### 第一步：进入目录

```bash
cd platform3
```

### 第二步：一键部署

```bash
# 基础部署（无认证）
bash init.sh

# 安全部署（ES/Kibana 认证 + 随机密码）
bash init.sh --secure

# 全功能部署（认证 + 监控）
bash init.sh --secure --monitor

# 全新部署（清除旧数据）
bash init.sh --reset --secure
```

> 首次运行需拉取镜像（约 2-3 GB），请等待 5-10 分钟。看到 `[OK]` 冒烟测试全部通过即部署完成。

### init.sh 参数一览

| 参数 | 作用 |
|------|------|
| `--secure` | 启用 ES/Kibana 认证，自动生成随机密码写入 `.env` |
| `--monitor` | 附加部署 Prometheus + Grafana 监控栈 |
| `--strict` | 严格模式，任一 init 容器失败则中止部署 |
| `--reset` | 删除所有数据卷，全新初始化 |
| `--skip-init` | 只启动服务，跳过初始化容器 |
| `--backup` | 执行数据备份（ES 快照 + Vault 导出 + .env） |
| `--restore PATH` | 从指定备份路径恢复数据 |

### .env 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `BIND_ADDRESS` | `127.0.0.1` | 服务端口绑定地址；设为 `0.0.0.0` 允许局域网访问 |
| `ES_MEM_LIMIT` | `3g` | ES 容器内存上限 |
| `ES_CPUS` | `2` | ES 容器 CPU 核数上限 |
| `ES_MEMORY` | `2g` | ES JVM 堆内存 |

### 部署后访问

| 服务 | 地址 | 说明 |
|------|------|------|
| Kibana | http://localhost:15601 | 统一可视化入口 |
| Elasticsearch | http://localhost:19200 | 日志后端 API |
| Vault UI | https://localhost:18200 | 凭证管理 |
| Grafana | http://localhost:3000 | 仅 `--monitor` |
| Prometheus | http://localhost:9090 | 仅 `--monitor` |

### 默认凭证

| 服务 | 用户名 | 密码 |
|------|--------|------|
| Vault | Token 登录 | 运行 `docker compose logs vault-init` 查看 |
| ES (--secure) | `elastic` | 见 `.env` 中 `ELASTIC_PASSWORD` |
| Kibana (--secure) | `kibana_system` | 见 `.env` 中 `KIBANA_ES_PASSWORD` |
| Grafana (--monitor) | `admin` | `platform3` |

---

## 3. 准备工作：安装 Docker

### Windows 系统

**方法一：Docker Desktop（推荐）**

1. 打开 [Docker Desktop 下载页](https://www.docker.com/products/docker-desktop/)
2. 点击 **Download for Windows**，下载安装包（约 600MB）
3. 双击安装包，一路点"下一步"
4. 安装完成后**重启电脑**
5. 重启后 Docker Desktop 自动启动（任务栏右下角鲸鱼图标）
6. 打开 **PowerShell**，验证安装：

```powershell
docker --version
```

**方法二：WSL2 + Docker**

如果你已启用 WSL2，在 WSL Ubuntu 终端中：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# 重新打开终端使权限生效
docker --version
```

### Linux 系统（Ubuntu/Debian）

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
```

### 验证 Docker 正常工作

```bash
docker run --rm hello-world
```

看到 `Hello from Docker!` 即安装成功。

---

## 4. 部署选项说明

### 4.1 一键部署（推荐）

```bash
bash init.sh --secure
```

`init.sh` 自动完成：检查 Docker -> 生成 TLS 证书 -> 启动服务 -> 等待 healthy -> 初始化 Vault/ILM/Kibana -> 创建 Dashboard -> API 冒烟测试。

### 4.2 按场景选择

```bash
bash init.sh                          # 最小部署（3 服务，无认证）
bash init.sh --secure                 # 加 ES/Kibana 认证
bash init.sh --secure --monitor       # 加认证 + Prometheus/Grafana
bash init.sh --reset --secure         # 清除旧数据全新部署
```

### 4.3 手动逐步部署

```bash
# 1. 生成证书
docker compose run --rm cert-init

# 2. 启动服务
docker compose up -d

# 3. 等待 healthy
docker compose ps

# 4. 依次初始化
docker compose run --rm ilm-init
docker compose run --rm vault-init
docker compose run --rm kibana-init
docker compose run --rm dashboard-init
```

---

## 5. 访问与演示

### 5.1 演示路线

#### 路线一：安全态势总览（推荐验收/汇报）

1. 打开 Kibana：http://localhost:15601
2. 左侧菜单 -> **Dashboard** -> 点击 **Platform Security Overview**
3. 右上角时间选择器 -> 选择 **Last 24 hours** 或 **Entire time range**
4. 展示：WAF 攻击类型分布、Suricata 告警时间线、威胁总数、攻击源 IP、威胁严重等级

#### 路线二：数据生命周期展示

1. Kibana -> **Dashboard** -> 点击 **Data Lifecycle Overview**
2. 展示：总文档数、NiFi 处理器状态、MinIO 存储桶分布、采集吞吐量

#### 路线三：按数据源检索

1. Kibana -> **Discover** -> 选择 Index Pattern
2. SafeLine WAF Records -> 查看 Web 攻击拦截记录
3. Suricata IDS Alerts -> 查看网络入侵检测告警
4. Vault Audit Logs -> 查看审计日志
5. MinIO Audit Logs -> 查看存储桶状态
6. NiFi Logs -> 查看数据流运行状态

### 5.2 Kibana 资产清单

| 类型 | 数量 | 名称 |
|------|------|------|
| Index Pattern | 5 | vault-audit-*, minio-audit-*, nifi-logs-*, safeline-records-*, suricata-alerts-* |
| Dashboard | 2 | Platform Security Overview, Data Lifecycle Overview |
| Saved Search | 5 | 每个数据源一个预置检索视图 |

---

## 6. 日志采集

### 一键采集

```bash
# 在所有服务运行的情况下
bash scripts/ingest-all.sh
```

### 单源采集

```bash
# 从 Platform 3 容器内运行
ES_URL=http://localhost:19200 python3 scripts/ingest-vault-audit.py
ES_URL=http://localhost:19200 python3 scripts/ingest-minio-audit.py
ES_URL=http://localhost:19200 python3 scripts/ingest-nifi-logs.py
ES_URL=http://localhost:19200 python3 scripts/ingest-safeline.py
ES_URL=http://localhost:19200 python3 scripts/ingest-suricata.py
```

### 日志清理

```bash
# 删除 30 天前的 ES 索引
bash scripts/cleanup-logs.sh 30

# 删除 7 天前的 ES 索引
bash scripts/cleanup-logs.sh 7
```

---

## 7. 常用操作

### 停止平台

```bash
docker compose down
```

所有容器停止，数据保留。

### 重新启动

```bash
docker compose up -d
```

无需再次初始化。

### 完全重置

```bash
docker compose down -v
```

然后重新运行 `bash init.sh --reset --secure`。

### 查看服务日志

```bash
docker compose logs elasticsearch
docker compose logs kibana
docker compose logs vault
docker compose logs -f          # 实时查看所有日志
```

### 重启服务

```bash
docker compose restart kibana
```

### 运行健康检查

```bash
docker compose run --rm health-check
```

### 备份数据

```bash
bash init.sh --backup
# 或手动
bash scripts/backup.sh
```

### 恢复数据

```bash
bash init.sh --restore backups/20260513-120000
# 或手动
bash scripts/restore.sh backups/20260513-120000
```

---

## 8. 故障排查

### Q: 端口被占用

A: Platform 3 使用独立端口（19200/15601/18200），避免与 Platform 1 冲突。如仍被占用，编辑 `.env` 或 `docker-compose.yml` 修改端口映射。

### Q: 某个服务一直是 unhealthy

A: 查看日志定位问题：
```bash
docker compose logs <服务名>
```

常见原因：
- **内存不足**：ES 默认需要 2GB。编辑 `.env` 将 `ES_MEMORY` 改为 `512m`
- **端口冲突**：检查是否有其他程序占用 19200/15601/18200 端口

### Q: Kibana 里没有数据

A:
1. 确认 ES 有索引：浏览器打开 http://localhost:19200/_cat/indices
2. 运行采集脚本：`bash scripts/ingest-all.sh`
3. 在 Kibana Discover 中选择对应 Index Pattern 查看

### Q: Vault 打不开

A: Vault 需要先初始化才能正常工作。确认 vault-init 已成功运行：
```bash
docker compose logs vault-init
```

### Q: 采集脚本报错

A: 采集脚本连接的是宿主机上的 Platform 1/2 服务（localhost:9000, 8443, 9443 等）。确保对应平台服务在运行。

### Q: 想卸载干净

A:
```bash
docker compose down -v          # 停止并删除所有数据
# 删除镜像释放空间：
docker rmi hashicorp/vault:1.21
docker rmi docker.elastic.co/elasticsearch/elasticsearch:9.4.0
docker rmi docker.elastic.co/kibana/kibana:9.4.0
```
