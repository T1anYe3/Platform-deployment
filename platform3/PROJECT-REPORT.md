# Platform 3 合规与应急响应平台 -- 项目交付报告

**生成日期**：2026年5月13日
**部署方式**：Docker Compose 容器化部署
**版本**：v2.0 -- Docker 增强版

---

## 一、项目概述

Platform 3（合规与应急响应平台）是三平台架构中的**统一日志汇聚与可视化层**。它从 Platform 1 和 Platform 2 服务中采集日志数据，通过 Elasticsearch 统一存储，Kibana 提供可视化检索和态势展示。

### 核心定位

- 日志能不能集中？ -- 5 个数据源统一写入 Elasticsearch
- 日志能不能检索？ -- Kibana Discover + 5 个 Index Pattern + 5 个 Saved Search
- 安全状态能不能看见？ -- 2 个统一 Dashboard
- 三平台统一展示？ -- 单一入口 http://localhost:15601 覆盖全部数据源

---

## 二、整体架构

```
                    +--------------------------------------+
                    |        Platform 3 Docker Stack        |
                    |                                       |
                    |  +----------+  +------------------+   |
                    |  |  Kibana  |  |  Elasticsearch   |   |
                    |  |  :15601  |  |     :19200       |   |
                    |  +----+-----+  +--------+---------+   |
                    |       |                 |             |
                    |       |    +------------+             |
                    |       |    |                          |
                    |  +----+----+-----+                    |
                    |  | Log Ingestion |                    |
                    |  |   Scripts     |                    |
                    |  +-------+-------+                    |
                    |          |                             |
                    |  +-------+-------+                    |
                    |  |    Vault      |                    |
                    |  |    :18200     |                    |
                    |  +---------------+                    |
                    +--------------------------------------+
                                    |
                    +---------------+---------------+
                    |               |               |
              +-----+-----+  +------+------+  +----+-----+
              | Platform1 |  |  Platform2  |  |  Wazuh   |
              | SafeLine  |  |   MinIO     |  | (Phase 2)|
              | Suricata  |  |   NiFi      |  |          |
              +-----------+  +-------------+  +----------+
```

### 数据流向

```
SafeLine WAF (P1)  --> ingest-safeline.py  --> ES safeline-records-*  --> Kibana
Suricata IDS (P1)  --> ingest-suricata.py  --> ES suricata-alerts-*   --> Kibana
Vault (本地)       --> ingest-vault-audit.py --> ES vault-audit-*      --> Kibana
MinIO (P2)         --> ingest-minio-audit.py --> ES minio-audit-*      --> Kibana
NiFi (P2)          --> ingest-nifi-logs.py   --> ES nifi-logs-*        --> Kibana
```

---

## 三、组件清单

### 3.1 Docker 服务（3+ 个）

| 服务 | 镜像 | 端口映射 | 说明 |
|------|------|---------|------|
| Elasticsearch | elasticsearch:9.4.0 | 19200:9200 | 单节点，统一日志后端 |
| Kibana | kibana:9.4.0 | 15601:5601 | 可视化与检索前端 |
| Vault | hashicorp/vault:1.21 | 18200:8200 | 轻量级凭证管理，TLS |
| Prometheus (可选) | prom/prometheus | 9090:9090 | 监控指标采集 |
| Grafana (可选) | grafana/grafana | 3000:3000 | 监控可视化 |

### 3.2 Init 容器（一次性）

| 容器 | 功能 |
|------|------|
| ilm-init | 创建 ILM 策略 + 5 个索引模板 |
| vault-init | 初始化 Vault + 启用审计日志 |
| kibana-init | 创建 5 个 Kibana Index Pattern |
| dashboard-init | 创建 2 个 Dashboard + 5 个 Saved Search |

### 3.3 采集脚本（5 个）

| 脚本 | 数据源 | 目标索引 | 连接 |
|------|--------|---------|------|
| ingest-vault-audit.py | Vault 审计日志 | vault-audit-* | localhost:18200 |
| ingest-minio-audit.py | MinIO 状态 | minio-audit-* | localhost:9000 |
| ingest-nifi-logs.py | NiFi 诊断 | nifi-logs-* | localhost:8443 |
| ingest-safeline.py | SafeLine WAF | safeline-records-* | localhost:9443 |
| ingest-suricata.py | Suricata IDS | suricata-alerts-* | eve.json 文件 |

---

## 四、5 大数据源字段标准化

所有数据源采用统一的 `event.source` 字段标识来源。

| 索引模式 | event.source | 核心字段 |
|---------|-------------|---------|
| vault-audit-* | vault | @timestamp, event.action, auth.display_name, request.operation, request.path |
| minio-audit-* | minio | @timestamp, event.action, minio.bucket, minio.objects, minio.status |
| nifi-logs-* | nifi | @timestamp, nifi.active_threads, nifi.processors_running, event.action |
| safeline-records-* | safeline | @timestamp, event_id, attack_type, src_ip, url_path, action, reason |
| suricata-alerts-* | suricata | @timestamp, alert.signature, alert.severity, src_ip, dest_ip |

---

## 五、Kibana 资产

### 5.1 Index Patterns（5 个）

vault-audit-*, minio-audit-*, nifi-logs-*, safeline-records-*, suricata-alerts-*

### 5.2 Dashboards（2 个）

| Dashboard | 描述 | 可视化数量 |
|-----------|------|-----------|
| Platform Security Overview | WAF + IDS 安全态势总览 | 6 个面板 |
| Data Lifecycle Overview | NiFi + MinIO + Vault 数据流监控 | 6 个面板 |

### 5.3 Saved Searches（5 个）

| 名称 | 数据源 | 预置列 |
|------|--------|--------|
| P3-Vault Audit Logs | vault-audit | @timestamp, event.action, auth.display_name, request.operation, request.path |
| P3-MinIO Audit Logs | minio-audit | @timestamp, event.action, minio.bucket, minio.objects, minio.status |
| P3-NiFi Logs | nifi-logs | @timestamp, nifi.active_threads, nifi.processors_running, event.action |
| P3-SafeLine WAF Records | safeline-records | @timestamp, attack_type, src_ip, url_path, action, reason |
| P3-Suricata IDS Alerts | suricata-alerts | @timestamp, alert.signature, alert.severity, src_ip, dest_ip |

---

## 六、ILM 日志生命周期

| 策略 | 热阶段 | 删除阶段 | 适用索引 |
|------|--------|---------|---------|
| platform3-logs-30d | 1天 / 5GB 滚动 | 30天自动删除 | 全部 5 个索引模板 |

---

## 七、KPI 指标

| 编号 | 指标 | 目标值 | 验证方式 |
|------|------|--------|---------|
| KPI-1 | 服务可用率 | 100% | health-check.sh |
| KPI-2 | 日志入库率 | >= 80% | ES _cat/indices |
| KPI-3 | 采集成功率 | >= 80% | ingest-all.sh |
| KPI-4 | Dashboard 可用率 | 100% | Kibana Saved Objects |
| KPI-5 | 字段标准化率 | 100% | ES mapping 检查 |

---

## 八、演示步骤

1. 启动：`bash init.sh --secure`
2. 健康检查：`docker compose run --rm health-check`
3. 采集日志：`bash scripts/ingest-all.sh`
4. 打开 Kibana：http://localhost:15601
5. Stack Management -> Index Patterns：展示 5 个已配置
6. Dashboard -> Platform Security Overview：安全态势总览
7. Dashboard -> Data Lifecycle Overview：数据流监控
8. Discover -> 依次展示 5 个 Saved Search

---

## 九、端口隔离

| 服务 | Platform 1 | Platform 3 |
|------|-----------|-----------|
| Elasticsearch | 9200 | 19200 |
| Kibana | 5601 | 15601 |
| Vault | 8200 | 18200 |

两组端口完全独立，可同时运行。

---

## 十、后续扩展

1. Wazuh 主机入侵检测（Linux VM / WSL2 部署）
2. pfSense 防火墙日志接入
3. ES Watcher 告警规则
4. RBAC 权限控制
5. ES 3 节点集群
