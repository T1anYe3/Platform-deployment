# Platform-deployment — 三平台安全防护体系 Docker 部署

一键部署三个分层协同的安全平台，构建完整的数据安全防护体系：

```
基础技术防护（安全底座） → 数据全生命周期管理（数据枢纽） → 合规与应急响应（统一展示）
```

---

## 三平台架构总览

```
 ┌────────────────────────── Platform 1 ──────────────────────────┐
 │  基础技术防护层 —— 安全底座                                     │
 │                                                                 │
 │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
 │  │ 加密与密钥    │ │ 证书管理      │ │ 网络边界      │            │
 │  │              │ │              │ │              │            │
 │  │ • 传输加密    │ │ • PKI 内建CA  │ │ • IDS/IPS    │            │
 │  │   TLS 1.3优先 │ │ • 自动签发/   │ │   Suricata   │            │
 │  │ • 应用层加密   │ │   吊销/轮换   │ │ • WAF 防护    │            │
 │  │   Vault Transit│ │ • 90-180天   │ │   SafeLine   │            │
 │  │   加密/解密/   │ │   证书有效期  │ │ • 安全域隔离  │            │
 │  │   签名/验签    │ │ • 到期告警    │ │   pfSense    │            │
 │  │ • 密钥生命周期 │ │ • mTLS 双向  │ │              │            │
 │  │   分级/轮换/   │ │   身份认证    │ │              │            │
 │  │   销毁/审计    │ │              │ │              │            │
 │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘            │
 │         │                │                │                     │
 │         └────────────────┼────────────────┘                     │
 │                          ▼                                      │
 │              凭据/证书/密钥 统一输出                              │
 └──────────────────────────┬──────────────────────────────────────┘
                            │ TLS证书、mTLS通道、加密密钥、审计日志
                            ▼
 ┌────────────────────────── Platform 2 ──────────────────────────┐
 │  数据全生命周期管理层 —— 数据枢纽                                │
 │                                                                 │
 │  ┌──────────────────────────────────────────────────────┐      │
 │  │              数据生命周期 8 阶段全覆盖                    │      │
 │  │                                                      │      │
 │  │  采集 ──→ 接入 ──→ 加工 ──→ 存储 ──→ 使用 ──→ 共享     │      │
 │  │    │       │       │       │       │       │          │      │
 │  │    ▼       ▼       ▼       ▼       ▼       ▼          │      │
 │  │  归档 ──→ 销毁                                       │      │
 │  │                                                      │      │
 │  │  NiFi 数据流编排: GetFile → UpdateAttribute → PutS3   │      │
 │  │  MinIO 6 层Bucket: raw→processed→model→eval→arch→audit │      │
 │  │  Vault 凭据集中: access_key, secret_key, 加密密钥       │      │
 │  └──────────────────────────────────────────────────────┘      │
 │                                                                 │
 │  数据流: 样本文件 → NiFi拾取 → 属性标记 → MinIO入湖 → ES索引    │
 └──────────────────────────┬──────────────────────────────────────┘
                            │ 运行日志、审计事件、Bucket状态
                            ▼
 ┌────────────────────────── Platform 3 ──────────────────────────┐
 │  合规与应急响应层 —— 统一展示与态势感知                           │
 │                                                                 │
 │  ┌──────────────────────────────────────────────────────┐      │
 │  │                 五源日志统一汇聚                         │      │
 │  │                                                      │      │
 │  │  SafeLine WAF ─┐                                     │      │
 │  │  Suricata IDS ─┤                                     │      │
 │  │  Vault Audit  ─┼──→ Elasticsearch ──→ Kibana         │      │
 │  │  MinIO Audit  ─┤        │                │           │      │
 │  │  NiFi Diag    ─┘        ▼                ▼           │      │
 │  │                    ILM 30天      2个Dashboard         │      │
 │  │                    自动清理      5个Saved Search      │      │
 │  └──────────────────────────────────────────────────────┘      │
 │                                                                 │
 │  事件闭环: 告警触发→研判→分派→控制→根因分析→修复→复盘归档        │
 │  告警分级: 严重(立即)→高危(2h)→中危(1d)→低危(3d)→提示(跟踪)    │
 └─────────────────────────────────────────────────────────────────┘
```

### 三平台协同关系

| 协同维度 | 平台1 → 平台2/3 | 说明 |
|----------|-----------------|------|
| **证书链路** | Vault PKI → NiFi/MinIO/ES/Kibana | 平台1 签发所有服务的 HTTPS/mTLS 证书 |
| **凭据链路** | Vault KV → platform2/* | NiFi、MinIO 访问凭据统一存储在 Vault |
| **加密链路** | Vault Transit → 应用层加密 | 应用数据通过 Transit 引擎加密/签名后传输 |
| **日志链路** | 全部平台 → ES → Kibana | 防火墙、IDS、审计、存储、编排日志统一汇入平台3 |
| **审计链路** | Vault 审计 → ES vault-audit-* | 所有凭据访问、密钥操作留痕可追溯 |

---

## 目录结构

```
Platform-deployment/
├── README.md                       # 本文件
├── .env.example                    # 环境变量模板
├── platform1/                      # 基础技术防护平台
│   ├── init.sh                     #   一键部署脚本
│   ├── docker-compose.yml          #   7 核心服务 + 可选监控
│   ├── docker-compose.monitoring.yml
│   └── ...
├── platform2/                      # 数据全生命周期管理平台
│   ├── init.sh
│   ├── docker-compose.yml          #   6 核心服务 + Bridge 管道
│   ├── BUILD-GUIDE.md              #   多平台构建规范
│   ├── 平台测试方法论.md             #   五轮测试标准
│   └── ...
└── platform3/                      # 合规与应急响应平台
    ├── init.sh
    ├── docker-compose.yml          #   3 核心服务 + 日志采集
    └── ...
```

---

## Platform 1 — 基础技术防护平台

> **定位**：安全底座。解决"数据如何安全传输、服务身份是否可信、密钥是否集中受控、异常流量是否可发现"。

### 1.1 核心能力

#### 加密与密钥管理

| 能力 | 实现方式 | 说明 |
|------|----------|------|
| **传输加密** | TLS 1.3 优先，TLS 1.2 兼容 | 禁用 SSLv2/3、TLS 1.0/1.1、弱密码套件 |
| **应用层加密** | Vault Transit 引擎 | 提供 encrypt / decrypt / sign / verify / rewrap 五种操作 |
| **密钥生命周期** | Vault KV + Transit | 创建 → 分级 → 轮换 → 禁用 → 销毁 → 审计，全流程受控 |
| **秘密存储** | Vault KV v2 | 数据库密码、API Token、应用配置口令集中管理，支持版本回滚 |
| **mTLS 双向认证** | Vault PKI 签发客户端证书 | 服务间调用启用客户端证书校验，杜绝未授权访问 |

**Vault Transit 加解密流程：**

```
明文数据 → [Vault Transit encrypt] → vault:v1:xxxx 密文 → 传输/存储 → [Vault Transit decrypt] → 明文数据
                ↑                                                                    ↑
           密钥永不离开 Vault                                               仅授权应用可解密
```

#### 证书生命周期管理

| 能力 | 实现方式 | 说明 |
|------|----------|------|
| **内部 CA** | Vault PKI 引擎 | 根 CA → 中间 CA → 服务/客户端证书，三级证书链 |
| **自动签发** | PKI Role（internal-service）| 支持 `sec.local`、`data.local`、`dmz.local` 等内部域名 |
| **自动吊销** | Vault PKI CRL | 证书泄露或服务下线时即时吊销 |
| **到期管理** | 90-180 天短效期 + 到期告警 | 提前 30 天、15 天、7 天分级提醒 |
| **基线审计** | testssl.sh | 对每个 HTTPS 入口执行 TLS 配置合规检查 |

#### 网络边界防护

| 能力 | 组件 | 检测/防护内容 |
|------|------|---------------|
| **入侵检测** | Suricata IDS/IPS | 明文 HTTP 访问敏感服务、非授权端口访问、TLS 降级尝试、异常证书/SNI、数据外发 |
| **Web 防护** | SafeLine WAF | SQL 注入、XSS、路径穿越、恶意扫描、API 滥用 |
| **安全域隔离** | pfSense | 管理区 / 数据处理区 / 安全监测区 / DMZ 四区隔离，默认拒绝，显式放行 |

### 1.2 安全指标体系

| 指标 | 数据源 | 目标值 |
|------|--------|--------|
| 加密覆盖率 | 资产台账 + TLS 扫描 | **100%** |
| 安全握手成功率 | TLS/mTLS 握手日志 | **≥ 99%** |
| 证书有效率 | Vault PKI + TLS 扫描 | **100%** |
| 明文传输违规率 | Suricata + Elastic 检索 | **0 或趋近 0** |
| 密钥轮换成功率 | Vault 审计日志 | **≥ 95%** |
| 异常阻断率 | 模拟攻击测试 | **100%** |

### 1.3 快速开始

```bash
cd platform1
bash init.sh --secure --monitor --with-safeline
```

| 服务 | 地址 | 提供能力 |
|------|------|----------|
| **Vault UI** | https://localhost:8200 | 密钥管理、证书签发、加密操作 |
| **Kibana** | http://localhost:5601 | 安全态势总览（Platform1 Security Overview） |
| **MinIO Console** | http://localhost:9001 | 对象存储管理 |
| **NiFi** | https://localhost:8443/nifi | 数据流编排 |
| **SafeLine WAF** | https://localhost:9443 | Web 应用防火墙 |

---

## Platform 2 — 数据全生命周期管理平台

> **定位**：数据枢纽。解决"数据从哪里来、流向哪里、谁处理过、存在哪里、如何归档销毁、过程是否可审计"。

### 2.1 核心能力

#### 数据接入与流编排

| 能力 | 实现方式 | 说明 |
|------|----------|------|
| **多格式接入** | NiFi GetFile / ListenHTTP | 支持 JSON、CSV、TXT 三种演示格式，可扩展数据库和消息队列 |
| **属性标记** | NiFi UpdateAttribute | 自动添加 `data.source`（来源）、`data.level`（密级）、`data.ingested`（入库时间） |
| **完整性校验** | NiFi HashContent | 对数据流计算 SHA-256 摘要，确保传输未篡改 |
| **血缘追踪** | NiFi Provenance | 记录每个 FlowFile 经过的所有处理器和持续时间 |
| **流模板** | platform2-demo-ingest | 一键部署 GetFile → UpdateAttribute → PutS3Object 演示流 |

**数据处理流程：**

```
sample-data/ 目录          NiFi 编排引擎                  MinIO 对象存储
┌──────────────┐     ┌─────────────────────────┐     ┌──────────────┐
│ JSON 日志文件  │────►│ GetFile (10s轮询)        │     │              │
│ CSV 传感器数据 │────►│   ↓                     │────►│ raw-data     │
│ TXT 审计记录  │────►│ UpdateAttribute (标记)    │    │ 90天自动过期  │
│              │     │   ↓                     │     │              │
│ 后续可扩展：   │     │ PutS3Object (入湖)       │     │ processed-   │
│ HTTP/Kafka/DB │     │   ↓                     │     │ data         │
│              │     │ 审计日志 → ES            │     │ 180天        │
└──────────────┘     └─────────────────────────┘     └──────────────┘
```

#### 数据全生命周期策略

平台2 覆盖数据的完整 8 阶段生命周期，每阶段有明确的技术控制点：

| 阶段 | 控制点 | 技术实现 |
|------|--------|----------|
| **采集** | 来源登记、通道加密、责任人标识 | NiFi GetFile/ListenHTTP + mTLS + 数据标签 |
| **接入** | 格式校验、摘要校验、恶意内容检测 | NiFi HashContent + ValidateRecord |
| **加工** | 脱敏、转换、加密、血缘记录 | NiFi Processor + Vault Transit |
| **存储** | 分桶隔离、版本控制、对象锁、服务端加密 | MinIO Bucket Policy + Vault KMS |
| **使用** | 最小权限、临时凭据、访问审批 | MinIO IAM + Vault Dynamic Secrets |
| **共享** | 水印、脱敏、用途限制、多方计算 | NiFi 路由 + SecretFlow（可选增强） |
| **归档** | 生命周期自动转储、冷存储、冻结 | MinIO ILM → archive-data (730天) |
| **销毁** | 删除审批、销毁证明、审计留痕 | MinIO Delete + ES 审计索引 |

#### 对象存储分层

| Bucket | 用途 | 生命周期 | 特殊策略 |
|--------|------|----------|----------|
| `raw-data` | 原始采集数据 | **90 天**自动过期 | 版本控制启用 |
| `processed-data` | 清洗/转换后数据 | **180 天**自动过期 | 版本控制启用 |
| `model-files` | ML 模型/权重文件 | **365 天**自动过期 | 对象锁（防误改） |
| `evaluation-results` | 评测结果 | **180 天**自动过期 | — |
| `archive-data` | 长期归档 | **730 天**自动过期 | 冷存储 |
| `audit-evidence` | 审计证据/导出记录 | 受控保留（不过期） | 建议启用 WORM 锁 |

#### 凭据集中管理

平台2 的所有敏感凭据存储在 Platform 1 的 Vault 中，不落地明文：

| Vault 路径 | 存储内容 |
|------------|----------|
| `secret/platform2/minio` | `access_key`、`secret_key`、`api_endpoint`、`console_endpoint` |
| `secret/platform2/nifi` | `admin_username`、`admin_password`、`api_endpoint`、`web_ui` |
| `secret/platform2/config` | `sample_data_dir`、`minio_bucket`、`data_classifications` |

#### 可视化监控

| 仪表板 | 展示内容 |
|--------|----------|
| **Data Lifecycle Overview** | 总文档数、采集吞吐量、各 Bucket 对象分布 |
| **MinIO Bucket Status** | 6 个 Bucket 的存储量、对象数、最后写入时间 |
| **NiFi Flow Status** | 处理器运行状态、数据流速率、错误计数 |

### 2.2 验收指标

| 验收项 | 目标值 |
|--------|--------|
| 数据源登记完整率 | ≥ 95% |
| 数据流可追踪率（血缘） | ≥ 95% |
| 存储加密覆盖率（高敏数据） | **100%** |
| 版本控制覆盖率（关键桶） | **100%** |
| 生命周期策略覆盖率 | ≥ 95% |
| 审计日志接入率（NiFi + MinIO + Vault） | **100%** |

### 2.3 快速开始

```bash
cd platform2
bash init.sh --secure
```

| 服务 | 地址 | 提供能力 |
|------|------|----------|
| **NiFi** | https://localhost:8443/nifi | 数据流编排、血缘追踪 |
| **MinIO Console** | http://localhost:9001 | 6 层 Bucket 管理、生命周期策略 |
| **Kibana** | http://localhost:5601 | 数据生命周期总览 Dashboard |
| **Vault UI** | https://localhost:8200 | 凭据管理（platform2 路径） |

**演示闭环步骤：**

1. 启动服务 → 2. 执行 `create-nifi-flow.ps1` 创建流模板 → 3. 在 NiFi 中启动处理器 → 4. 查看 MinIO raw-data bucket 中的对象 → 5. 在 Kibana 查看 Data Lifecycle Overview

---

## Platform 3 — 合规与应急响应平台

> **定位**：统一展示与态势感知。解决"安全事件能否看见、告警能否定位、配置是否合规、事件是否能闭环"。

### 3.1 核心能力

#### 五源日志汇聚

平台3 从 Platform 1 和 Platform 2 采集 5 个数据源的日志，统一写入 Elasticsearch：

| 数据源 | ES 索引 | 关键字段 | 来源平台 |
|--------|---------|----------|----------|
| **SafeLine WAF** | `safeline-records-*` | `attack_type`, `src_ip`, `url_path`, `action`, `event.source=safeline` | Platform 1 |
| **Suricata IDS** | `suricata-alerts-*` | `alert.signature`, `alert.severity`, `src_ip`, `dest_ip`, `event.source=suricata` | Platform 1 |
| **Vault 审计** | `vault-audit-*` | `auth.display_name`, `request.operation`, `request.path`, `event.source=vault` | Platform 1/2 |
| **MinIO 状态** | `minio-audit-*` | `event.action`, `minio.bucket`, `minio.objects`, `event.source=minio` | Platform 2 |
| **NiFi 诊断** | `nifi-logs-*` | `event.action`, `nifi.active_threads`, `nifi.processors_running`, `event.source=nifi` | Platform 2 |

**日志标准化**：所有记录包含统一的 `@timestamp`（时间）和 `event.source`（来源）字段，支持跨源联查。ILM 策略自动管理 30 天日志保留与清理。

#### 统一态势感知

| Kibana 资产 | 类型 | 用途 |
|-------------|------|------|
| **Platform Security Overview** | Dashboard | WAF 攻击类型分布、Suricata 告警时间线、威胁总数、攻击源 IP Top-N、威胁严重等级饼图 |
| **Data Lifecycle Overview** | Dashboard | 总文档数、NiFi 处理器状态、MinIO Bucket 分布、采集吞吐量趋势 |
| **SafeLine Attack Blocks (24h)** | Saved Search | 最近 24 小时 WAF 拦截记录 |
| **Suricata Realistic Alerts (24h)** | Saved Search | 最近 24 小时 IDS 告警记录 |
| **Vault Audit Trail** | Saved Search | Vault 操作审计追溯 |
| **NiFi System Diagnostics** | Saved Search | NiFi 系统资源与线程状态 |
| **MinIO Bucket Status** | Saved Search | Bucket 存储统计 |

#### 告警分级与响应 SLA

| 等级 | 示例事件 | 处置时限 |
|------|----------|----------|
| **严重** | Vault root token 异常使用、关键密钥被删除、管理入口暴力破解成功 | **立即处置** |
| **高危** | 明文传输敏感数据、MinIO 高敏桶公开访问、Suricata 高危攻击告警 | **2 小时内** |
| **中危** | 证书即将过期（≤7天）、NiFi 数据流连续失败、主机存在高危漏洞 | **1 个工作日内** |
| **低危** | 非关键配置漂移、异常登录失败、磁盘容量预警 | **3 个工作日内** |
| **提示** | 日常策略命中、低风险扫描、例行审计信息 | **例行跟踪** |

#### 事件闭环处置流程

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ 1.告警触发 │──→│ 2.初步研判 │──→│ 3.分派处置 │──→│ 4.临时控制 │
│ ES/Wazuh  │   │ 确认影响   │   │ 指派责任人 │   │ 阻断/吊销/ │
│ 产生告警   │   │ 范围与密级 │   │           │   │ 隔离/禁用  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                   │
┌──────────┐   ┌──────────┐   ┌──────────┐        │
│ 7.复盘归档 │←──│ 6.修复整改 │←──│ 5.根因分析 │←───────┘
│ 事件记录   │   │ 补丁/加固/ │   │ 检索日志   │
│ 证据包/复测 │   │ 权限收敛   │   │ 关联分析   │
└──────────┘   └──────────┘   └──────────┘
```

#### 合规映射

将技术控制映射到合规要求，实现可检查、可审计：

| 合规要求 | 技术落点 | 检查方式 |
|----------|----------|----------|
| 日志留存 | ES ILM 30 天 + 备份 | 检查索引生命周期策略和快照 |
| 访问控制 | pfSense + Vault + MinIO + NiFi | 检查策略配置和账号权限审计 |
| 加密传输 | TLS 1.3/mTLS/VPN | testssl.sh 扫描 + 连接日志统计 |
| 密钥管理 | Vault PKI + Transit + KV | 检查密钥轮换记录和审计日志 |
| 文件完整性 | Wazuh FIM（二阶段扩展） | FIM 告警和基线报告 |
| 漏洞管理 | Wazuh（二阶段扩展） | 漏洞检测报告 |
| 事件响应 | ES 告警 + 工单流程 | 事件记录和复盘报告 |

### 3.2 验收指标

| 验收项 | 目标值 |
|--------|--------|
| 日志接入覆盖率（关键服务） | **100%** |
| 告警有效性（可触发、可定位） | 通过模拟测试 |
| 主机检测覆盖率（Wazuh Agent 在线率） | ≥ 95%（二阶段） |
| 文件完整性监控（FIM） | 可告警 |
| 事件闭环 | 有记录、有整改、有复测 |

### 3.3 快速开始

```bash
cd platform3
bash init.sh --secure
```

| 服务 | 地址 | 提供能力 |
|------|------|----------|
| **Kibana** | http://localhost:15601 | 五源日志检索、2 个 Dashboard、5 个 Saved Search |
| **Elasticsearch** | http://localhost:19200 | 统一日志后端，ILM 30 天自动清理 |
| **Vault UI** | https://localhost:18200 | 轻量凭证管理 |

> Platform 3 使用独立端口（ES:19200, Kibana:15601, Vault:18200）避免与 Platform 1/2 冲突，三平台可同时运行。

---

## 部署架构建议

### 推荐节点规格

| 节点类型 | 建议配置 | 承载组件 |
|----------|----------|----------|
| 安全网关节点 | 4C / 8G / 双网卡 | pfSense、Suricata |
| 密钥与证书节点 | 4C / 8G / 100G SSD | Vault（生产建议 3 节点 HA） |
| 数据流编排节点 | 8C / 16G / 200G SSD | NiFi（生产建议集群 + 外部 ZooKeeper） |
| 对象存储节点 | 8C / 16G / 独立数据盘 | MinIO（生产建议 4 节点分布式） |
| 日志分析节点 | 8C / 32G / 500G SSD+ | Elasticsearch（生产建议 3 节点 + 冷热分层） |
| 主机检测节点 | 4C / 8G / 200G SSD | Wazuh Manager + Dashboard |

### 网络安全域划分

| 安全域 | 典型组件 | 访问策略 |
|--------|----------|----------|
| **管理区** | Vault、Kibana、Wazuh Dashboard、NiFi UI | 仅允许运维/审计来源 |
| **数据处理区** | NiFi、MinIO、业务处理服务 | 禁止直接暴露外网 |
| **安全监测区** | Suricata、ES、Wazuh | 接收日志，不主动发起连接 |
| **DMZ** | SafeLine、反向代理、API 网关 | 对外暴露，严格限制后端访问 |

---

## 技术栈总览

| 组件 | 版本 | 用途 | 所属平台 |
|------|------|------|----------|
| HashiCorp Vault | 1.21 | 密钥管理、PKI、加密服务 | P1 / P2 / P3 |
| Elasticsearch | 9.4.0 | 日志存储与检索 | P1 / P2 / P3 |
| Kibana | 9.4.0 | 可视化仪表板 | P1 / P2 / P3 |
| Apache NiFi | 2.3.0 / 2.9.0 | 数据流编排与血缘 | P1 / P2 |
| MinIO | latest | S3 兼容对象存储 | P2 |
| SafeLine WAF | Community | Web 应用防火墙 | P1 |
| Suricata | 8.0.3 | IDS/IPS 入侵检测 | P1 |
| Prometheus | — | 监控指标采集 | P1 / P2 / P3（可选） |
| Grafana | — | 监控可视化 | P1 / P2 / P3（可选） |

---

## 文档索引

| 文档 | 路径 |
|------|------|
| Platform 1 详细文档 | [platform1/README.md](platform1/README.md) |
| Platform 2 详细文档 | [platform2/README.md](platform2/README.md) |
| Platform 3 详细文档 | [platform3/README.md](platform3/README.md) |
| 多组件构建规范 | [platform2/BUILD-GUIDE.md](platform2/BUILD-GUIDE.md) |
| 五轮测试方法论 | [platform2/平台测试方法论.md](platform2/平台测试方法论.md) |

---

## 快速开始（三平台同时部署）

```bash
# 克隆仓库
git clone https://github.com/T1anYe3/Platform-deployment.git
cd Platform-deployment

# 平台1：基础技术防护（7 核心 + WAF + IDS + 监控）
cd platform1 && bash init.sh --secure --monitor --with-safeline && cd ..

# 平台2：数据全生命周期管理（6 核心 + Bridge 管道）
cd platform2 && bash init.sh --secure && cd ..

# 平台3：合规与应急响应（3 核心 + 五源日志汇聚）
cd platform3 && bash init.sh --secure && cd ..
```

> **前提**：Docker Desktop / Docker Engine 已安装，8GB+ 可用内存，20GB+ 可用磁盘。

---

## 许可证

MIT License — 详见 [LICENSE](platform1/LICENSE)
