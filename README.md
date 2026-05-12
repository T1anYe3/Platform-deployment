# Platform 1 — 基础技术防护平台 Docker 部署指南

> 本指南面向**零 Docker 基础**的用户。从安装 Docker 到完成平台演示，每一步都有详细说明。

---

## 目录

1. [平台简介](#1-平台简介)
2. [准备工作：安装 Docker](#2-准备工作安装-docker)
3. [获取部署文件](#3-获取部署文件)
4. [部署平台](#4-部署平台)
5. [验证部署](#5-验证部署)
6. [访问与演示](#6-访问与演示)
7. [常用操作](#7-常用操作)
8. [故障排查](#8-故障排查)

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

部署完成后，所有组件将自动协同工作：Suricata 检测异常流量 → 日志写入 Elasticsearch → Kibana 可视化展示。

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

### 方式一：U 盘/文件夹拷贝（推荐给新手）

将整个 `platform1-docker/` 文件夹拷贝到你的电脑上任意位置（**路径不要包含中文**），例如：

```
C:\platform1-docker\        (Windows)
~/platform1-docker/         (Mac/Linux)
```

### 方式二：Git 下载

```bash
git clone https://github.com/T1anYe3/Platform-deployment.git
cd Platform-deployment
```

---

## 4. 部署平台

### 确保在正确目录

打开终端（Windows 用 PowerShell，Mac/Linux 用 Terminal），进入 `platform1-docker` 文件夹：

```bash
cd platform1-docker
```

> Windows 用户：如果文件夹在 D 盘，先执行 `D:` 切换到 D 盘再 `cd platform1-docker`

### 第一步：配置密码（可选但建议）

用记事本或任意文本编辑器打开 `.env` 文件，修改以下密码：

```
MINIO_ROOT_PASSWORD=你的密码（至少8位）
NIFI_ADMIN_PASS=你的密码（至少12位）
```

> 如果只是自己测试，也可以不改，用默认密码。

### 第二步：生成平台内部证书

```bash
docker compose run --rm cert-init
```

你会看到类似这样的输出，说明证书生成成功：

```
[cert-init] Generating Platform 1 Root CA...
[cert-init] Generating certificate for: vault
[cert-init] Generating certificate for: nifi
[cert-init] Generating certificate for: minio
[cert-init] All certificates generated successfully.
```

### 第三步：启动所有服务

```bash
docker compose up -d
```

> `-d` 表示后台运行。首次启动需要**下载镜像**（约 3-5 GB），请耐心等待 5-15 分钟，取决于你的网速。

**查看启动进度**（可以另开一个终端窗口）：

```bash
docker compose logs -f
```

按 `Ctrl+C` 退出日志查看（不会停止服务）。

**等待所有服务就绪**：

```bash
docker compose ps
```

当所有服务的 `STATUS` 列显示 `healthy` 时，说明平台启动完成。这个过程需要 3-5 分钟（ES 和 NiFi 启动较慢）。

### 第四步：初始化平台组件

依次执行以下命令（每次等上一步完成再执行下一个）：

```bash
# 1. 初始化 Vault（密钥管理引擎）
docker compose run --rm vault-init

# 2. 初始化 MinIO（创建存储桶和过期策略）
docker compose run --rm minio-init

# 3. 初始化 Kibana（创建数据视图和仪表板）
docker compose run --rm kibana-init

# 4. 初始化 NiFi（导入数据流模板）
docker compose run --rm nifi-init
```

看到每条命令输出 `complete` 或 `setup complete` 就说明初始化成功。

---

## 5. 验证部署

### 一键健康检查

```bash
docker compose run --rm health-check
```

输出示例：

```
========================================
  Platform 1 Docker Health Check
========================================
  [UP]    Vault            :8200
  [UP]    Elasticsearch    :9200
  [UP]    Kibana           :5601
  [UP]    MinIO API        :9000
  [UP]    MinIO Console    :9001
  [UP]    NiFi             :8443
  Summary: 6 UP, 0 DOWN
```

### 手动抽查

在浏览器中访问以下地址确认服务正常：

| 地址 | 预期看到什么 |
|------|-------------|
| http://localhost:9200 | 一个 JSON 文本，包含 `cluster_name` 和 `version` |
| http://localhost:5601 | Kibana 首页界面 |
| http://localhost:9001 | MinIO 登录页面 |

---

## 6. 访问与演示

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

## 7. 常用操作

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

然后从[部署平台](#4-部署平台)的第二步重新开始。

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

## 8. 故障排查

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
