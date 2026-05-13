# Platform 2 数据全生命周期管理平台测试方案

## 1. 测试目标

验证 Platform 2 Docker 部署在以下维度的数据全生命周期能力：

1. **服务可用性**: 6 个核心服务正常启动并可通过端口访问
2. **TLS 安全性**: Vault/NiFi/MinIO 使用 TLS 加密通信
3. **密钥管理**: Vault 正确存储和提供组件凭证
4. **对象存储**: MinIO 6 个桶创建正确，生命周期策略生效
5. **数据流编排**: NiFi 流程组正确创建，处理器链可用
6. **数据管道**: Bridge Runner 正确采集数据入 ES
7. **可视化**: Kibana 索引模式和仪表板正确创建
8. **数据生命周期**: ILM 策略和 MinIO 过期策略配置正确

---

## 2. 测试环境

### 2.1 硬件要求

- CPU: 4 核+
- RAM: 8GB+
- 磁盘: 20GB+ 可用空间

### 2.2 软件要求

- Docker Desktop / Docker Engine 24+
- Docker Compose v2+
- Bash (Git Bash on Windows)

---

## 3. 测试用例

### TC-01: 一键部署测试

**步骤**:
```bash
cd platform2
bash init.sh --secure
```

**预期结果**:
- 所有 6 个核心服务容器启动并达到 healthy
- Init 容器依次运行成功
- 无错误输出
- API 冒烟测试全部 [OK]

**验证**:
```bash
docker compose ps
```

---

### TC-02: 服务端口可达性测试

**步骤**: 分别访问以下 URL

| 服务 | URL | 预期响应码 |
|------|-----|-----------|
| Elasticsearch | http://localhost:9200 | 200 |
| Kibana | http://localhost:5601/api/status | 200 |
| MinIO API | https://localhost:9000/minio/health/live | 200 |
| MinIO Console | http://localhost:9001 | 200 |
| Vault | https://localhost:8200/v1/sys/health | 200 |
| NiFi | https://localhost:8443/nifi-api/system-diagnostics | 200 |

**验证**:
```bash
docker compose run --rm health-check
```

---

### TC-03: TLS 证书验证

**步骤**:
1. 检查 Vault 使用 HTTPS：`curl -k https://localhost:8200/v1/sys/health`
2. 检查 NiFi 使用 HTTPS：`curl -k https://localhost:8443/nifi-api/access/config`
3. 检查 MinIO API 使用 HTTPS：`curl -k https://localhost:9000/minio/health/live`

**预期结果**: 三个服务均支持 HTTPS 连接（自签证书，使用 `-k` 跳过验证）

---

### TC-04: Vault 密钥存储测试

**步骤**:
1. 获取 root token（从 init 日志）
2. 登录 Vault UI: https://localhost:8200
3. 验证 secrets engine:
   ```bash
   docker compose exec vault vault secrets list -tls-skip-verify
   ```

**预期结果**:
- `secret/` (kv-v2) 已启用
- `pki/` 已启用
- `transit/` 已启用
- `secret/platform2/minio` 存储了 MinIO 凭证
- `secret/platform2/nifi` 存储了 NiFi 凭证
- `secret/platform2/config` 存储了平台配置

---

### TC-05: MinIO 桶创建与生命周期测试

**步骤**:
1. 登录 MinIO Console: http://localhost:9001
2. 确认 6 个桶已存在
3. 检查生命周期规则

**预期结果**:

| 桶名 | 状态 | 过期天数 |
|------|------|---------|
| raw-data | 已创建 | 90 |
| processed-data | 已创建 | 180 |
| model-files | 已创建 | 365 |
| evaluation-results | 已创建 | 180 |
| archive-data | 已创建 | 730 |
| audit-evidence | 已创建 | 受控保留 |

**验证**:
```bash
docker compose exec minio mc ls platform2/
```

---

### TC-06: NiFi 流程组测试

**步骤**:
1. 登录 NiFi UI: https://localhost:8443/nifi
2. 查看根流程组下的 `platform2-demo-ingest` 子组

**预期结果**:
- 流程组 `platform2-demo-ingest` 存在
- 包含 3 个处理器：GetFile-Ingest, UpdateAttribute-Enrich, PutS3Object-MinIO
- 处理器间已建立连接（有 success 关系线）

---

### TC-07: Bridge 数据管道测试

**步骤**:
1. 等待 Bridge Runner 运行至少 1 个周期
2. 检查 ES 索引
3. 检查 Bridge 日志

**预期结果**: 以下索引存在数据：
- `platform2-vault-audit-YYYY.MM.DD`
- `platform2-minio-audit-YYYY.MM.DD`
- `platform2-nifi-logs-YYYY.MM.DD`

**验证**:
```bash
curl -s http://localhost:9200/_cat/indices?v | grep platform2
```

---

### TC-08: Kibana 仪表板测试

**步骤**:
1. 打开 Kibana: http://localhost:5601
2. 导航到 Dashboard 列表

**预期结果**: 存在以下仪表板：
- Platform 2 Data Lifecycle Overview
- Platform 2 MinIO Bucket Status
- Platform 2 NiFi Flow Status

**预期结果**: 存在以下索引模式：
- Platform 2 Vault Audit Logs (platform2-vault-audit-*)
- Platform 2 MinIO Audit Logs (platform2-minio-audit-*)
- Platform 2 NiFi System Logs (platform2-nifi-logs-*)

---

### TC-09: ILM 策略测试

**步骤**:
```bash
curl -s http://localhost:9200/_ilm/policy/* | python3 -m json.tool
```

**预期结果**: 存在 3 个 ILM 策略：
- `platform2-vault-audit-policy` (hot:30d warm:90d delete:180d)
- `platform2-minio-audit-policy` (hot:30d warm:90d delete:180d)
- `platform2-nifi-logs-policy` (hot:30d warm:90d delete:180d)

---

### TC-10: KPI 基准测试

**步骤**:
```bash
python3 scripts/security-benchmark.py --full
```

**预期结果**: 6 项 KPI 全部 PASS

---

## 4. 测试结果记录模板

| 用例 | 描述 | 预期 | 实际 | 状态 |
|------|------|------|------|------|
| TC-01 | 一键部署 | 6 服务 healthy | | |
| TC-02 | 端口可达 | 6 端点 200 | | |
| TC-03 | TLS 证书 | 3 服务 HTTPS | | |
| TC-04 | Vault 密钥 | 3 类 secret | | |
| TC-05 | MinIO 桶 | 6 桶 + 生命周期 | | |
| TC-06 | NiFi 流程 | 3 处理器已连接 | | |
| TC-07 | Bridge 管道 | 3 索引有数据 | | |
| TC-08 | Kibana 仪表板 | 3 仪表板+3 索引模式 | | |
| TC-09 | ILM 策略 | 3 ILM 策略 | | |
| TC-10 | KPI 基准 | 6/6 PASS | | |

---

## 5. 清理与重测

```bash
# 完全清理
cd platform2
docker compose down -v

# 重新测试
bash init.sh --reset --secure
```
