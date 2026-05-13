# Platform 2 数据全生命周期管理平台 -- 最终交付报告

> 版本 1.0 | 2026-05-13 | Docker 部署  
> `bash init.sh --secure`  
> 核心容器: **6** | 含 init 容器: **13**

---

## 1. 项目概述

Platform 2 是面向数据全生命周期管理的 Docker 化部署平台，实现从数据采集、流转处理、对象存储、日志检索到可视化监控的完整闭环。

### 核心能力

- **密钥管理**: Vault 集中管理所有组件凭证与加密密钥
- **对象存储**: MinIO 提供 6 个数据全生命周期桶，支持 90 天到 730 天的分层保留
- **数据流编排**: Apache NiFi 实现数据采集、转换、分发流程
- **日志存储**: Elasticsearch 存储平台运营日志和审计事件
- **可视化**: Kibana 提供 3 个专用仪表板：数据生命周期总览、MinIO 桶状态、NiFi 流状态
- **数据管道**: Bridge Runner 持续采集 Vault/MinIO/NiFi 运行数据入 ES

---

## 2. 架构设计

### 2.1 数据流向

```
外部数据源
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  NiFi (数据流编排)                                     │
│  GetFile -> UpdateAttribute -> PutS3Object             │
│  数据采集 → 属性标注 → MinIO 存储                      │
└──────────────────┬───────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌────────┐  ┌───────────┐  ┌──────────┐
│ 6 数据桶│  │ Vault     │  │ ES/Kibana│
│ MinIO  │  │ 密钥/审计  │  │ 可视化   │
└───┬────┘  └─────┬─────┘  └────┬─────┘
    │             │              │
    └──────┬──────┘              │
           │                     │
    ┌──────▼─────────────────────▼──────┐
    │     Bridge Runner (数据管道)       │
    │  bridge-minio.py  (60s interval)   │
    │  bridge-nifi.py   (120s interval)  │
    │  bridge-vault.py  (300s interval)  │
    └────────────────┬──────────────────┘
                     │
                     ▼
            Elasticsearch
           (平台运行日志)
                     │
                     ▼
         Kibana (3 Dashboard)
```

### 2.2 组件映射

| 组件 | 内部地址 | 外部端口 | TLS |
|------|---------|----------|-----|
| Vault | https://vault:8200 | 8200 | 是 |
| Elasticsearch | http://elasticsearch:9200 | 9200 | 否 |
| Kibana | http://kibana:5601 | 5601 | 否 |
| MinIO | https://minio:9000 | 9000/9001 | 是 |
| NiFi | https://nifi:8443 | 8443 | 是 |
| Bridge | 内部运行 | - | - |

### 2.3 网络设计

- Docker 内部网络: `platform2` (bridge driver)
- 容器间通信: 通过 Docker 服务名（如 `http://vault:8200`）
- 外部访问: 端口映射到 `localhost`（可通过 `BIND_ADDRESS` 配置）

---

## 3. KPI 定义与评估

Platform 2 定义了 6 项数据全生命周期关键绩效指标：

| KPI | 指标名称 | 计算公式 | 目标值 |
|-----|---------|---------|--------|
| KPI-1 | 安全传输率 | TLS 启用服务数 / 需 TLS 服务总数 x 100% | >= 95% |
| KPI-2 | 数据入库率 | 有数据的 ES 索引数 / 预期索引总数 x 100% | >= 99% |
| KPI-3 | 管道事件率 | 活跃桥接源数 / 总桥接源数 x 100% | >= 90% |
| KPI-4 | 审计覆盖率 | (Vault 审计日志条数 > 0) ? 100 : 0 | 100% |
| KPI-5 | 证书合规率 | 有效 TLS 证书数 / TLS 服务总数 x 100% | 100% |
| KPI-6 | 数据吞吐量 | 50MB 文件上传耗时计算 MB/s | >= 10 MB/s |

运行基准测试：
```bash
python3 scripts/run-full-benchmark.py
```

---

## 4. 访问地址汇总

| 服务 | URL | 说明 |
|------|-----|------|
| Kibana | http://localhost:5601 | 可视化主界面 |
| MinIO Console | http://localhost:9001 | 对象存储管理 |
| Vault UI | https://localhost:8200 | 密钥管理界面 |
| NiFi UI | https://localhost:8443/nifi | 数据流设计界面 |
| Elasticsearch | http://localhost:9200 | 后端 API |
| DL Overview Dashboard | http://localhost:5601/app/dashboards#/view/platform2-data-lifecycle | 数据生命周期总览 |
| MinIO Status Dashboard | http://localhost:5601/app/dashboards#/view/platform2-minio-status | 存储桶状态 |
| NiFi Status Dashboard | http://localhost:5601/app/dashboards#/view/platform2-nifi-status | 数据流状态 |

---

## 5. 演示步骤

### 5.1 部署启动

```bash
cd platform2
bash init.sh --secure
```

等待所有服务 healthy（约 3-5 分钟），init 容器依次运行。

### 5.2 验证访问

1. 打开 **MinIO Console** (http://localhost:9001)，使用 `minioadmin / ChangeThis-Local-123!` 登录
2. 确认 6 个数据桶已创建：raw-data, processed-data, model-files, evaluation-results, archive-data, audit-evidence
3. 打开 **NiFi UI** (https://localhost:8443/nifi)，使用 `admin / Admin123!ChangeMe` 登录
4. 确认 `platform2-demo-ingest` 流程组已创建，包含 GetFile -> UpdateAttribute -> PutS3Object
5. 打开 **Kibana** (http://localhost:5601)，查看 3 个仪表板

### 5.3 演示数据管道

1. 生成测试数据：`python3 scripts/generate-test-data.py`
2. 将 CSV/JSON 文件放入 NiFi 输入目录
3. 启动 NiFi 流程，观察数据经过 UpdateAttribute 标注后写入 MinIO raw-data 桶
4. Bridge Runner 自动采集 MinIO 桶状态和 NiFi 系统诊断入 ES
5. 在 Kibana 仪表板中查看实时数据

### 5.4 演示数据生命周期

1. 演示 MinIO 桶的过期策略：raw-data(90d) / processed-data(180d) / archive-data(730d)
2. 演示 audit-evidence 桶的不可变保留（如已启用对象锁定）
3. 演示 ES ILM 策略：热(30d) -> 温(60d) -> 删(90d)

---

## 6. 容器清单

### 核心服务容器 (6)

| 容器名 | 镜像 | 内存限制 |
|--------|------|---------|
| platform2-vault | hashicorp/vault:1.21 | 512m |
| platform2-elasticsearch | elasticsearch:9.4.0 | 3g |
| platform2-kibana | kibana:9.4.0 | 1g |
| platform2-minio | minio/minio:latest | 512m |
| platform2-nifi | apache/nifi:2.3.0 | 2g |
| platform2-bridge | 自建 (python:3.12-alpine) | 256m |

### Init 容器 (7，运行后退出)

cert-init, es-users-init, ilm-init, vault-init, dashboard-init, minio-init, kibana-init, nifi-init, health-check

---

## 7. 数据卷清单

| 卷名 | 用途 |
|------|------|
| tls-data | TLS 证书（自签 Root CA + 服务证书） |
| vault-data | Vault 加密存储、审计日志 |
| es-data | Elasticsearch 索引数据 |
| minio-data | MinIO 对象存储数据（6 个桶） |
| nifi-data | NiFi 流程定义、状态数据 |
| nifi-flow | NiFi 流程定义快照 |
| bridge-state | Bridge Runner 状态文件 |

---

## 8. 安全措施

- TLS 加密：Vault、NiFi、MinIO 使用自签证书（SHA-256, 3650 天有效期）
- 密钥管理：所有凭证存储在 Vault kv-v2 引擎中
- 审计日志：Vault 文件审计日志通过 bridge 采集入 ES
- 访问控制：Vault ACL 策略限制组件对 secret/ 的访问权限
- 密码随机生成：--secure 模式下使用 openssl rand 生成随机密码
- .env 不入 Git：通过 .gitignore 排除

---

## 9. 文件清单

参见 README.md 项目结构章节。

---

## 10. 总结

Platform 2 数据全生命周期管理平台已完整实现以下能力：

- [x] 6 个容器化组件 (Vault + ES + Kibana + MinIO + NiFi + Bridge)
- [x] 一键部署入口 (bash init.sh --secure)
- [x] TLS 全覆盖 (自签 CA，Vault/NiFi/MinIO)
- [x] 6 个 MinIO 数据桶 + 层级生命周期策略
- [x] 3 个 Kibana 仪表板 (数据生命周期/桶状态/流状态)
- [x] Bridge 数据管道持续采集运行数据
- [x] Vault 密钥存储 + 审计日志
- [x] ES ILM 自动过期策略
- [x] 功能健康检查和 KPI 基准测试
- [x] 数据备份/恢复脚本
- [x] 可选 Prometheus + Grafana 监控栈
