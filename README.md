# Platform-deployment — 三平台安全防护体系 Docker 部署

一键部署三个互补平台，构建完整的数据安全防护体系：**基础技术防护 → 数据全生命周期管理 → 合规与应急响应**。

---

## 三平台架构总览

```
Platform 1 (安全防护层)          Platform 2 (数据管理层)          Platform 3 (合规展示层)
┌─────────────────────┐      ┌─────────────────────┐      ┌─────────────────────┐
│ Vault  统一凭据管理    │◄────│ Vault  凭据集成       │      │ ES    统一日志后端    │
│ ES     日志存储       │─────►│ ES     日志存储       │─────►│ Kibana 统一可视化     │
│ Kibana 仪表板        │      │ Kibana 仪表板        │      │ Vault  轻量凭据       │
│ MinIO  对象存储       │      │ MinIO  6 Bucket+ILM │      │ 5源日志接入管道       │
│ NiFi   数据流编排      │      │ NiFi   数据流模板     │      │ 3个统一Dashboard     │
│ Suricata IDS检测     │      │ Bridge 3数据管道      │      │ ILM 30天生命周期      │
│ SafeLine WAF防护     │      │                     │      │                     │
└─────────────────────┘      └─────────────────────┘      └─────────────────────┘
```

---

## 快速开始

```bash
git clone https://github.com/T1anYe3/Platform-deployment.git
cd Platform-deployment
```

### Platform 1 — 基础技术防护（7 核心 + WAF + IDS + 监控）

```bash
cd platform1
bash init.sh --secure --monitor --with-safeline
```

| 服务 | 地址 |
|------|------|
| Kibana | http://localhost:5601 |
| MinIO Console | http://localhost:9001 |
| Vault UI | https://localhost:8200 |
| NiFi | https://localhost:8443/nifi |
| SafeLine WAF | https://localhost:9443 |

### Platform 2 — 数据全生命周期管理（6 核心 + Bridge）

```bash
cd platform2
bash init.sh --secure
```

| 服务 | 地址 |
|------|------|
| Kibana | http://localhost:5601 |
| MinIO Console | http://localhost:9001 |
| Vault UI | https://localhost:8200 |
| NiFi | https://localhost:8443/nifi |

### Platform 3 — 合规与应急响应（3 核心 + 日志汇聚）

```bash
cd platform3
bash init.sh --secure
```

| 服务 | 地址 |
|------|------|
| Kibana | http://localhost:15601 |
| Elasticsearch | http://localhost:19200 |
| Vault UI | https://localhost:18200 |

> **注意**：Platform 3 使用独立端口（19200/15601/18200）避免与 Platform 1/2 冲突。三平台可同时运行。


## 目录结构

```
Platform-deployment/
├── README.md                 # 本文件
├── platform1/                # 基础技术防护平台
│   ├── init.sh
│   ├── docker-compose.yml
│   ├── README.md
│   └── ...
├── platform2/                # 数据全生命周期管理平台
│   ├── init.sh
│   ├── docker-compose.yml
│   ├── README.md
│   └── ...
└── platform3/                # 合规与应急响应平台
    ├── init.sh
    ├── docker-compose.yml
    ├── README.md
    └── ...
```

## 文档

- [Platform 1 详细文档](platform1/README.md)
- [Platform 2 详细文档](platform2/README.md)
- [Platform 3 详细文档](platform3/README.md)
- [构建指南](platform2/BUILD-GUIDE.md) — 适用于所有平台的 Docker 构建规范
- [测试方法论](platform2/平台测试方法论.md) — 五轮测试标准与工具

## 许可证

MIT License — 详见 [LICENSE](platform1/LICENSE)
