# Platform 3 可用性测试方案

## 1. 测试目标

验证 Platform 3 Docker 部署在以下维度的能力：

- **服务可用性**：ES、Kibana、Vault 能否正常启动并通过健康检查
- **日志采集能力**：5 个采集脚本能否从各数据源正确采集数据并写入 ES
- **可视化能力**：Index Pattern、Dashboard、Saved Search 是否创建成功
- **日志管理能力**：ILM 策略是否正确生效，清理脚本是否正常工作
- **运维能力**：备份恢复、健康检查脚本是否正常工作

## 2. KPI 指标体系

| 编号 | 指标 | 计算公式 | 目标值 | 数据来源 |
|------|------|---------|--------|---------|
| KPI-1 | 服务可用率 | healthy 服务数 / 总服务数 x 100% | 100% | health-check.sh |
| KPI-2 | 日志入库率 | 有数据索引数 / 5 个预期索引 x 100% | >= 80% | ES _cat/indices |
| KPI-3 | 采集成功率 | 成功采集的源数 / 5 个总源 x 100% | >= 80% | ingest-all.sh 输出 |
| KPI-4 | Dashboard 可用率 | 创建成功的 Dashboard 数 / 2 个预期 x 100% | 100% | Kibana Saved Objects API |
| KPI-5 | Index Pattern 可用率 | 已创建的 Pattern 数 / 5 个预期 x 100% | 100% | Kibana Saved Objects API |

## 3. 测试步骤

### 前置条件

```bash
# 1. 确认 Docker 运行
docker info

# 2. 进入 platform3 目录
cd platform3

# 3. 部署平台
bash init.sh --secure
```

### 场景 A：服务可用性测试

**目标**：验证 3 个核心服务全部 healthy

```bash
# 检查服务状态
docker compose ps

# 运行健康检查
docker compose run --rm health-check
```

**预期结果**：
- Elasticsearch: UP, 返回 cluster_name
- Kibana: UP, 返回 Kibana 状态信息
- Vault: UP, 返回 initialized 状态
- 3/3 UP

### 场景 B：Kibana 资产验证

**目标**：验证 Index Pattern、Dashboard、Saved Search 创建成功

```bash
# 在浏览器中验证：
# 1. 打开 http://localhost:15601
# 2. Stack Management -> Index Patterns
#    预期：5 个 Index Pattern 全部显示
# 3. Dashboard
#    预期：Platform Security Overview + Data Lifecycle Overview
# 4. Discover -> Open
#    预期：5 个 Saved Search 可选
```

**预期结果**：
- 5 个 Index Pattern 已创建
- 2 个 Dashboard 可访问
- 5 个 Saved Search 可使用

### 场景 C：日志采集测试

**目标**：验证 5 个采集脚本能正常运行

```bash
# 运行全部采集
bash scripts/ingest-all.sh
```

**预期结果**：
- 至少 1-2 个数据源采集成功（依赖 Platform 1/2 服务运行状态）
- Vault 审计日志采集成功（本地服务）
- 无脚本崩溃或 Python 异常

### 场景 D：日志入库验证

**目标**：验证采集的数据已写入 ES

```bash
# 检查所有索引
curl -s http://localhost:19200/_cat/indices?v

# 检查各索引的文档数
for idx in vault-audit minio-audit nifi-logs safeline-records suricata-alerts; do
  echo -n "${idx}: "
  curl -s "http://localhost:19200/${idx}-*/_count" | grep -o '"count":[0-9]*'
done
```

**预期结果**：
- 至少 vault-audit-* 索引有数据
- 索引按日期分片（vault-audit-YYYY.MM.DD）

### 场景 E：ILM 策略验证

**目标**：验证 ILM 策略已创建并关联到索引模板

```bash
# 查看 ILM 策略
curl -s http://localhost:19200/_ilm/policy/platform3-logs-30d | python3 -m json.tool

# 查看索引模板
for prefix in vault-audit minio-audit nifi-logs safeline-records suricata-alerts; do
  echo "=== ${prefix} ==="
  curl -s "http://localhost:19200/_index_template/${prefix}-template" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  index_patterns:', d.get('index_templates',[{}])[0].get('index_template',{}).get('index_patterns','N/A'))"
done
```

**预期结果**：
- platform3-logs-30d 策略包含 hot 和 delete 阶段
- 5 个索引模板均已创建，关联 platform3-logs-30d

### 场景 F：备份恢复测试

**目标**：验证备份和恢复流程正常工作

```bash
# 1. 运行采集（确保有数据）
bash scripts/ingest-all.sh

# 2. 备份
bash scripts/backup.sh

# 3. 检查备份产物
ls -la backups/
```

**预期结果**：
- backups/ 目录下有按时间戳命名的备份目录
- 包含 manifest.json, .env.backup, volumes.json

### 场景 G：日志清理测试

**目标**：验证清理脚本语法正确

```bash
# 预览（不实际删除，查看逻辑）
bash scripts/cleanup-logs.sh 365
```

**预期结果**：
- 脚本正常执行，显示"Checking"和"Keep"信息
- 无语法错误

## 4. Kibana 可视化验证清单

| 验证项 | Kibana 路径 | 检查内容 |
|--------|------------|---------|
| Index Patterns | Stack Management -> Index Patterns | 5 个全部列出 |
| Security Dashboard | Dashboard -> Platform Security Overview | 包含 6 个面板 |
| Data Lifecycle Dashboard | Dashboard -> Data Lifecycle Overview | 包含 6 个面板 |
| SafeLine Search | Discover -> P3-SafeLine WAF Records | 按 attack_type 筛选 |
| Suricata Search | Discover -> P3-Suricata IDS Alerts | 按 alert.severity 筛选 |
| Vault Search | Discover -> P3-Vault Audit Logs | 按 event.action 筛选 |
| MinIO Search | Discover -> P3-MinIO Audit Logs | 按 minio.bucket 筛选 |
| NiFi Search | Discover -> P3-NiFi Logs | 按 nifi.processors_running 筛选 |

## 5. 通过标准

| 等级 | 条件 |
|------|------|
| 优秀 | 5/5 KPI 全部 PASS |
| 良好 | 4/5 KPI PASS |
| 合格 | 3/5 KPI PASS |
| 不合格 | < 3 KPI PASS |

## 6. 端口冲突检查

Platform 3 使用独立端口避免与 Platform 1 冲突：

| 服务 | Platform 1 | Platform 3 | 状态 |
|------|-----------|-----------|------|
| Elasticsearch | 9200 | 19200 | 隔离 |
| Kibana | 5601 | 15601 | 隔离 |
| Vault | 8200 | 18200 | 隔离 |

验证：同时运行 Platform 1 和 Platform 3 时上述端口不冲突。
