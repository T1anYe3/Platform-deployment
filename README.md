# Platform 1 — 基础技术防护平台 Docker 部署指南

> **一键部署**：`bash init.sh --secure --monitor --with-safeline`

---

## 目录

1. [⚡ 快速开始（推荐）](#-快速开始推荐)
2. [平台简介](#1-平台简介)
3. [准备工作：安装 Docker](#2-准备工作安装-docker)
4. [获取部署文件](#3-获取部署文件)
5. [部署选项说明](#4-部署选项说明)
6. [访问与演示](#5-访问与演示)
7. [常用操作](#6-常用操作)
8. [故障排查](#7-故障排查)

---

## ⚡ 快速开始（推荐）

### 第一步：安装 Docker

```bash
# Windows: 下载 Docker Desktop → https://www.docker.com/products/docker-desktop/
# Mac: 同上
# Linux: curl -fsSL https://get.docker.com | sudo sh
docker --version  # 验证安装
```

### 第二步：获取代码

```bash
git clone https://github.com/T1anYe3/Platform-deployment.git
cd Platform-deployment
```

### 第三步：一键部署

```bash
# 全功能部署（认证 + 监控 + WAF + 安全规则集）
bash init.sh --secure --monitor --with-safeline

# 基础部署（6 个核心服务，无需认证）
bash init.sh

# 全新部署（清除旧数据）
bash init.sh --reset --secure --monitor --with-safeline
```

> 首次运行需拉取镜像（约 5-8 GB），请等待 10-20 分钟。看到 `[OK]` 冒烟测试全部通过即部署完成。

### `init.sh` 参数一览

| 参数 | 作用 |
|------|------|
| `--secure` | 启用 ES/Kibana 认证，自动生成随机密码写入 `.env` |
| `--monitor` | 附加部署 Prometheus + Grafana 监控栈 |
| `--with-safeline` | 附加部署 SafeLine CE（雷池 WAF，7 容器） |
| `--reset` | 删除所有数据卷，全新初始化 |
| `--skip-init` | 只启动服务，跳过 4 个初始化容器 |
| `--backup` | 执行数据备份（ES 快照 + Vault 导出 + .env） |
| `--restore PATH` | 从指定备份路径恢复数据 |

### 部署后访问

| 服务 | 地址 | 说明 |
|------|------|------|
| Kibana | http://localhost:5601 | 安全仪表板 |
| MinIO Console | http://localhost:9001 | 对象存储管理 |
| Vault UI | https://localhost:8200 | 密钥管理 |
| NiFi | https://localhost:8443/nifi | 数据流编排 |
| Grafana | http://localhost:3000 | 仅 `--monitor` |
| Prometheus | http://localhost:9090 | 仅 `--monitor` |
| SafeLine WAF | https://localhost:9443 | 仅 `--with-safeline` |

### 默认凭证

| 服务 | 用户名 | 密码 |
|------|--------|------|
| MinIO | `minioadmin` | 见 `.env` 中 `MINIO_ROOT_PASSWORD` |
| NiFi | `admin` | 见 `.env` 中 `NIFI_ADMIN_PASS` |
| SafeLine | `admin` | `docker exec safeline-mgt resetadmin` 查看 |
| Vault | Token 登录 | 见 `docker compose logs vault-init` 末尾 |
| Grafana | `admin` | `platform1` |
| ES (--secure) | `elastic` | 见 `.env` 中 `ELASTIC_PASSWORD`（自动生成） |

### 如果没有 SafeLine

不加 `--with-safeline` 即可跳过 WAF 部署，其余 6 个核心服务正常运行。

---

## 1. 平台简介

Platform 1（基础技术防护平台）包含以下组件：

| 组件 | 用途 | 访问地址 |
|------|------|---------|
| Vault | 证书/密钥/秘密管理 | https://localhost:8200 |
| Elasticsearch | 日志存储与检索 | http://localhost:9200 |
| Kibana | 可视化仪表板 | http://localhost:5601 |
| MinIO | 对象存储 | http://localhost:9001 |
| NiFi | 数据流编排 | https://localhost:8443/nifi |
| Suricata | 网络入侵检测 | （后台运行） |
| SafeLine WAF | Web 应用防火墙 | https://localhost:9443 |
| Prometheus | 监控指标采集 | http://localhost:9090 |
| Grafana | 监控可视化 | http://localhost:3000 |

部署完成后，所有组件将自动协同工作：WAF/IDS 检测攻击 → Bridge 采集日志 → Elasticsearch 存储 → Kibana 可视化展示。

---

## 2. 准备工作：安装 Docker

### 什么是 Docker？

Docker 就像一个"轻量级虚拟机"，它把程序和它需要的所有依赖打包在一起，你只需要一条命令就能在任何电脑上运行，不用手动安装和配置每个软件。

### Windows 系统

**方法一：Docker Desktop（推荐）**

1. 打开 [Docker Desktop 下载页](https://www.docker.com/products/docker-desktop/)
2. 点击 **Download for Windows**，下载安装包（约 600MB）
3. 双击安装包，一路点"下一步"，保持默认选项
4. 安装完成后**重启电脑**
5. 重启后 Docker Desktop 会自动启动（任务栏右下角会出现鲸鱼图标 🐳）
6. 打开 **PowerShell**（右键开始菜单 → Windows PowerShell），运行以下命令验证安装成功：

```powershell
docker --version
```

如果看到 `Docker version 2x.x.x` 就说明安装成功了。

**方法二：WSL2 + Docker（已有 WSL2 的情况）**

如果你已经启用了 WSL2（比如之前部署过 SafeLine），在 WSL 的 Ubuntu 终端中：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# 重新打开终端使权限生效
docker --version  # 验证
```

### macOS 系统

1. 打开 [Docker Desktop 下载页](https://www.docker.com/products/docker-desktop/)
2. 根据芯片类型选择：
   - **Apple Silicon**（M1/M2/M3/M4）→ 下载 Apple Chip 版本
   - **Intel** 芯片 → 下载 Intel Chip 版本
3. 双击 `.dmg` 文件，将 Docker 图标拖入 Applications 文件夹
4. 从 Launchpad 启动 Docker Desktop
5. 打开**终端**（Terminal），运行：

```bash
docker --version
```

### Linux 系统（Ubuntu/Debian）

```bash
# 一键安装
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# 注销重新登录，或运行：
newgrp docker
docker --version  # 验证
```

### 验证 Docker 正常工作

在所有系统上，运行以下命令：

```bash
docker run --rm hello-world
```

看到 `Hello from Docker!` 就说明安装完全成功。

---

## 3. 获取部署文件

### 方式一：Git 克隆（推荐）

```bash
git clone https://github.com/T1anYe3/Platform-deployment.git
cd Platform-deployment
```

### 方式二：下载 ZIP

在 https://github.com/T1anYe3/Platform-deployment 点击 **Code → Download ZIP**，解压到不含中文的路径。

---

## 4. 部署选项说明

### 4.1 一键部署（推荐）

```bash
bash init.sh --secure --monitor --with-safeline
```

`init.sh` 自动完成：生成证书 → 启动全部服务 → 等待 healthy → 初始化 Vault/MinIO/Kibana/NiFi → ES ILM 策略 → Dashboard 面板 → API 冒烟测试。

### 4.2 按场景选择

```bash
bash init.sh                                    # 最小部署（6 服务，无认证）
bash init.sh --secure                           # 加 ES/Kibana 认证
bash init.sh --secure --monitor                 # 加认证 + 监控
bash init.sh --secure --with-safeline           # 加认证 + WAF
bash init.sh --secure --monitor --with-safeline # 全功能
```

### 4.3 手动逐步部署（备选）

如果你需要完全控制每一步，可以手动执行：

```bash
# 1. 配置密码（可选）
notepad .env

# 2. 生成证书
docker compose run --rm cert-init

# 3. 启动服务
docker compose up -d

# 4. 等待 healthy（约 3-5 分钟）
docker compose ps

# 5. 依次初始化
docker compose run --rm vault-init
docker compose run --rm minio-init
docker compose run --rm kibana-init
docker compose run --rm nifi-init
```

---

## 5. 访问与演示

部署完成、健康检查全部通过后，可以开始演示平台功能。

### 6.1 各组件登录信息

| 组件 | 访问地址 | 用户名 | 密码 |
|------|---------|--------|------|
| Kibana | http://localhost:5601 | 无需登录 | — |
| Elasticsearch | http://localhost:9200 | 无需登录 | — |
| MinIO Console | http://localhost:9001 | `minioadmin` | 见 `.env` 中 `MINIO_ROOT_PASSWORD` |
| Vault UI | https://localhost:8200 | Token 登录 | 见下方获取方式 |
| NiFi | https://localhost:8443/nifi | 见 `.env` 中 `NIFI_ADMIN_USER` | 见 `.env` 中 `NIFI_ADMIN_PASS` |

> **获取 Vault Root Token**：查看 `docker compose logs vault-init` 输出的最后一行，或进入容器执行 `cat /vault/data/init-output.json`

### 6.2 演示路线

#### 路线一：安全事件可视化（推荐给验收/汇报）

1. 打开 Kibana：http://localhost:5601
2. 左侧菜单 → **Dashboard** → 点击 **Platform1 Security Overview**
3. 右上角时间选择器 → 选择 **Last 24 hours** 或 **Entire time range**
4. 展示仪表板中的各项安全指标

#### 路线二：数据全生命周期演示

1. 打开 MinIO Console：http://localhost:9001，登录
2. 左侧 **Buckets** → 可以看到 6 个已创建的存储桶（raw-data, processed-data 等）
3. 打开 NiFi：https://localhost:8443/nifi，登录
4. 展示预设的数据流模板（GetFile → UpdateAttribute → PutS3Object）

#### 路线三：查看安全事件详情

1. 打开 Kibana → 左侧菜单 → **Discover**
2. 在数据视图下拉菜单中选择 **Suricata IDS Alerts**
3. 可以看到 Suricata 检测到的网络告警（sqlmap 扫描、Nikto 扫描、敏感文件探测）
4. 切换到 **SafeLine WAF Records** 查看 Web 攻击拦截记录

### 6.3 手动产生测试数据

如果 Suricata 没有数据（可能因为网络环境限制），可以手动执行桥接脚本导入：

```bash
# 手动触发数据采集（依次执行）
docker compose exec bridge python3 /scripts/bridge-suricata.py
docker compose exec bridge python3 /scripts/bridge-vault.py
docker compose exec bridge python3 /scripts/bridge-minio.py
docker compose exec bridge python3 /scripts/bridge-nifi.py
```

然后刷新 Kibana Discover 页面，选择对应数据视图查看结果。

---

## 6. 常用操作

### 停止平台

```bash
docker compose down
```

所有容器停止，但**数据保留**（下次启动数据还在）。

### 重新启动

```bash
docker compose up -d
```

无需再次初始化——之前的配置和数据都在。

### 完全重置（清除所有数据）

```bash
docker compose down -v
```

然后从[部署选项说明](#4-部署选项说明)重新开始，或直接运行 `bash init.sh --reset --secure`。

### 查看某个服务的日志

```bash
docker compose logs elasticsearch    # ES 日志
docker compose logs vault            # Vault 日志
docker compose logs bridge           # 数据桥接日志
docker compose logs -f               # 实时查看所有日志
```

### 重启某个服务

```bash
docker compose restart kibana
```

---

## 7. 故障排查

### Q: 执行 `docker compose up -d` 后一直卡着不动

A: 这是正常的。首次启动需要从 Docker Hub 下载镜像（约 3-5 GB）。如果有进度条显示，说明正在下载。国内用户如果下载很慢，可以配置 Docker 镜像加速器（参考 [Docker 中国镜像加速配置](https://yeasy.gitbook.io/docker_practice/install/mirror)）。

### Q: `docker compose` 命令提示 `command not found`

A: 你可能用的是旧版 Docker。尝试用 `docker-compose`（带连字符）代替 `docker compose`（带空格）。如果还是不行，重新安装 Docker Desktop 最新版。

### Q: 端口被占用

A: 如果 9200、5601 等端口已被占用，编辑 `.env` 文件或 `docker-compose.yml` 修改端口映射。例如将 `"9200:9200"` 改为 `"19200:9200"`，然后通过 `http://localhost:19200` 访问。

### Q: 某个服务一直是 `unhealthy` 或反复重启

A: 查看该服务的日志定位问题：
```bash
docker compose logs <服务名>
```
例如：
```bash
docker compose logs elasticsearch
```

常见原因：
- **内存不足**：ES 默认需要 2GB 内存。如果电脑内存 < 8GB，编辑 `.env` 将 `ES_MEMORY` 改为 `512m`
- **端口冲突**：检查是否有其他程序占用 9200/5601/8200/9000/9001/8443 端口

### Q: Windows 上 MinIO 端口 9000 报错

A: Windows 的 Hyper-V 可能保留了 9000 端口。编辑 `docker-compose.yml`，将 `"9000:9000"` 改为 `"19000:9000"`，然后通过 `http://localhost:19000` 访问 MinIO API。

### Q: Mac Apple Silicon (M1/M2/M3/M4) 兼容性问题

A: 所有镜像都支持 ARM64 架构，应该可以直接运行。如果遇到 `exec format error` 错误，说明拉取了错误的架构镜像，确保 Docker Desktop 设置中未勾选 "Use Rosetta for x86/amd64 emulation"（用原生 ARM 镜像即可）。

### Q: Kibana 里没有数据

A: 
1. 确认 bridge 容器在运行：`docker compose ps bridge`
2. 手动触发采集：`docker compose exec bridge python3 /scripts/bridge-suricata.py`
3. 确认 ES 中有索引：浏览器打开 http://localhost:9200/_cat/indices 查看

### Q: 想卸载干净

A:
```bash
docker compose down -v          # 停止并删除所有数据
# 如果想删除镜像（释放磁盘空间）：
docker rmi hashicorp/vault:1.21
docker rmi docker.elastic.co/elasticsearch/elasticsearch:9.4.0
docker rmi docker.elastic.co/kibana/kibana:9.4.0
docker rmi minio/minio:latest
docker rmi apache/nifi:2.3.0
docker rmi jasonish/suricata:latest
```
