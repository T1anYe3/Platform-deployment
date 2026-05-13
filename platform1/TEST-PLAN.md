# Platform 1 可用性测试方案

## 1. 测试目标

验证 Platform 1 Docker 部署在以下维度的安全能力：
- **安全传输**：服务间通信是否加密
- **威胁检测**：IDS/WAF 对攻击流量的识别能力
- **证书管理**：Vault PKI 的证书签发与合规
- **审计完整性**：操作日志的完整覆盖
- **数据处理**：大规模数据流的吞吐量与可靠性

## 2. 安全指标体系

| 编号 | 指标 | 计算公式 | 目标值 | 数据来源 |
|------|------|---------|--------|---------|
| KPI-1 | 安全传输率 | TLS服务数 / 总服务数 × 100% | ≥ 95% | 端口TLS扫描 |
| KPI-2 | 威胁检测率 | 触发SID数 / 预期SID数 × 100% | ≥ 90% | ES suricata-alerts |
| KPI-3 | 证书合规率 | Vault证书服务数 / TLS服务总数 × 100% | 100% | TLS证书校验 |
| KPI-4 | 审计覆盖率 | 已审计操作 / 总操作数 × 100% | 100% | ES vault-audit |
| KPI-5 | 事件入库率 | 有数据的索引数 / 预期索引数 × 100% | ≥ 99% | ES索引统计 |
| KPI-6 | 数据吞吐量 | 传输量(MB) / 耗时(s) | ≥ 10 MB/s | MinIO mc cp |

## 3. 测试数据规格（总计 ~2 GB）

| 文件 | 大小 | 格式 | 记录数（约） | 用途 |
|------|------|------|-------------|------|
| bench-256m.json | 256 MB | JSON Lines | ~50万 | 结构化日志模拟 |
| bench-256m.csv | 256 MB | CSV | ~200万行 | 传感器数据模拟 |
| bench-512m.mixed | 512 MB | 混合 | ~300万 | 多格式混合数据 |
| bench-1g.bin | ~1 GB | 二进制 | — | 大文件吞吐测试 |

### 攻击流量规格

| 类型 | 数量 | 匹配规则 |
|------|------|---------|
| sqlmap User-Agent | 6000 | SID 9900101 |
| Nikto User-Agent | 6000 | SID 9900102 |
| /etc/passwd 探测 | 6000 | SID 9900103 |
| SQL注入 | 4000 | 额外攻击 |
| XSS | 4000 | 额外攻击 |
| 命令注入 | 4000 | 额外攻击 |
| 扫描器探测 | 4000 | 额外攻击 |
| 正常流量（混合） | 20000 | 不触发 |

## 4. 测试步骤

### 前置条件

```bash
# 1. 确认服务运行
cd platform1-docker
docker compose ps
# 预期：vault, elasticsearch, kibana, minio, nifi, suricata 全部 healthy

# 2. 初始化（如首次）
docker compose run --rm vault-init
docker compose run --rm minio-init
docker compose run --rm kibana-init
docker compose run --rm nifi-init
```

### 场景 A：安全传输率测试

**目标**：验证所有服务端口的 TLS 状态

```bash
# 运行TLS基准测试
python scripts/security-benchmark.py --metric tls
```

**预期结果**：
- Vault (8200): TLS detected
- MinIO (9000/9001): 视配置
- 安全传输率报告 >= 95%

### 场景 B：威胁检测闭环测试

**目标**：发送 5 万条攻击流量，验证 Suricata 检测 → ES 入库 → Kibana 可视化

```bash
# Step 1: 生成攻击流量（在bridge容器或宿主机运行）
pip install requests  # 如果 bridge 容器有 pip

# Step 2: 发送攻击流量
python scripts/generate-attack-traffic.py --target 127.0.0.1 --port 80 --num-attacks 50000 --normal-ratio 0.3

# Step 3: 等待 bridge-suricata 采集（60s间隔）
sleep 60

# Step 4: 检查检测结果
curl -s http://localhost:9200/suricata-alerts-*/_count | python -m json.tool

# Step 5: 按 SID 统计告警分布
curl -s -X POST http://localhost:9200/suricata-alerts-*/_search -H 'Content-Type: application/json' -d '{"size":0,"aggs":{"sids":{"terms":{"field":"alert.signature_id"}}}}' | python -m json.tool

# Step 6: 运行检测率基准测试
python scripts/security-benchmark.py --metric threat
```

**预期结果**：
- SID 9900101/9900102/9900103 三个规则全部触发
- 告警总数 > 10,000
- 威胁检测率 >= 90%

### 场景 C：数据吞吐量测试

**目标**：测量 NiFi→MinIO 管道在 GB 级数据下的吞吐量

```bash
# Step 1: 生成测试数据
python scripts/generate-test-data.py --output-dir /tmp/platform1-benchmark-data --total-size 2.0

# Step 2: 运行吞吐量测试
python scripts/security-benchmark.py --metric throughput
```

**预期结果**：
- 数据吞吐量 >= 10 MB/s
- 文件完整性校验通过（MD5/SHA256 前后一致）

### 场景 D：审计完整性测试

**目标**：验证 Vault 所有操作被审计日志记录

```bash
# Step 1: 运行审计基准测试
python scripts/security-benchmark.py --metric audit

# Step 2: 手动检查 Vault 审计日志
curl -s http://localhost:9200/vault-audit-*/_count

# Step 3: 检查审计日志覆盖的操作类型
curl -s -X POST http://localhost:9200/vault-audit-*/_search -H 'Content-Type: application/json' -d '{"size":0,"aggs":{"types":{"terms":{"field":"type"}}}}' 
```

**预期结果**：
- Vault 审计条目 > 0
- 审计覆盖全部操作类型（request/response）

### 场景 E：全量基准测试

```bash
# 一键运行全部 6 项指标
python scripts/security-benchmark.py --full

# 查看报告
cat /tmp/platform1-benchmark-results.json
```

## 5. Kibana 可视化验证

测试完成后，打开 Kibana 验证：

| 验证项 | Kibana 路径 | 检查内容 |
|--------|------------|---------|
| Suricata 告警 | Discover → Suricata IDS Alerts | 按 SID 统计告警趋势 |
| Vault 审计 | Discover → Vault Audit Logs | 操作类型分布 |
| MinIO 状态 | Discover → MinIO Audit Logs | bucket 对象数统计 |
| NiFi 诊断 | Discover → NiFi Logs | 线程数和队列状态 |
| 安全总览 | Dashboard → Platform1 Security Overview | 统一态势面板 |

## 6. 通过标准

| 等级 | 条件 |
|------|------|
| 优秀 | 6/6 指标全部 PASS |
| 良好 | 5/6 指标 PASS |
| 合格 | 4/6 指标 PASS |
| 不合格 | < 4 指标 PASS |
