# 部署指南（Docker & 本地命令行）

> 版本：v19.3（与 v19.2 功能一致，仅补齐文档）

---

## 1. 系统要求
- OS：Linux / macOS（Apple Silicon/Intel 均可）。
- Docker：Docker Desktop ≥ 4.19（或服务器 Docker Engine ≥ 24）。
- 端口：Prometheus 指标默认 `:9000`（可改）。
- 可选：本地运行需要 Python ≥ 3.10。

> Apple Silicon（M1/M2/M4）无需额外设置，镜像为多架构。若遇到镜像架构报错，可在 `docker build`/`compose` 时加 `--platform linux/arm64/v8`。

---

## 2. 目录结构（解压后）

```
.
├── Dockerfile
├── docker-compose.yml               # 单服务（组合交易）
├── docker-compose.multi.yml         # 多服务（交易+自动调参+指标）
├── .env.example                     
├── qi.yaml                          # 主配置（组合、执行、风控）
├── portfolio.yaml                   # 组合清单（兼容）
├── calendar.yaml                    # 交易日历/时段
├── live_output/                     # 日志与热加载配置目录（宿主机挂载）
├── quant_intraday/                  # 包源码（可 pip 安装）
└── docs/
    ├── QUICKSTART.md
    ├── CLI.md
    ├── ALERTS.md
    ├── RUNBOOK.md
    ├── CONFIG.md
    └── DEPLOYMENT.md                # 本文
```

---

## 3. 环境变量（`.env`）

复制模板并填写：
```bash
cp .env.example .env
```

关键变量：
- `OKX_API_KEY / OKX_API_SECRET / OKX_API_PASSPHRASE`：交易密钥。
- `OKX_SIMULATED=1`：**模拟盘**开关（建议先演练 24–48h）。
- `OKX_ACCOUNT=trade`：账户标识（兼容旧逻辑）。
- `QI_LOG_DIR=/app/live_output`：容器内日志/热加载目录（不要改动）。
- `QI_WEBHOOK_URL=`：可选，风控/熔断等事件回调地址。
- `TZ=Asia/Tokyo`：推荐设置，统一日志时区。

> 安全建议：不要把 `.env` 提交到代码仓库；生产使用 Docker/K8s Secret 更佳。

---

## 4. Docker 部署

### 4.1 单服务（最简）
```bash
docker compose up -d --build
```
- 默认命令：`qi run --cfg qi.yaml`（按主配置启动**组合实盘**）。
- 数据与热加载配置在宿主 `./live_output`。

### 4.2 多服务（推荐）
```bash
docker compose -f docker-compose.multi.yml up -d --build
```
- `trader`：组合实盘编排（BTC/ETH/SOL，可改 `qi.yaml`）。
- `autopilot`：每小时自调（权重/冷却/阈值 + Kelly 风险缩放）。
- `metrics`：Prometheus 指标（默认 `:9000`）。

### 4.3 上线前自检（必须）
```bash
docker compose run --rm trader qi doctor
# 通过后：
cat live_output/preflight.json   # 确认 "ok": true
```

### 4.4 日常运维
```bash
docker compose ps
docker compose logs -f trader
docker compose down && docker compose up -d
docker compose build --no-cache && docker compose up -d   # 升级/重新构建
```
健康检查：
```bash
# 单服务 compose 已启用 Dockerfile HEALTHCHECK
docker inspect --format='{{.State.Health.Status}}' $(docker ps -q --filter name=trader)
```

---

## 5. 本地命令行运行（不通过 Docker）

### 5.1 安装
```bash
pip install -e .
qi version
```

### 5.2 自检 & 运行
```bash
qi doctor                  # 配置+连通性预检
qi run --cfg qi.yaml       # 按主配置启动组合
# 或单品种：
qi live --inst BTC-USDT-SWAP --tf 5m --strategy auto --exec-mode autoexec
```

> 建议使用虚拟环境（venv/conda）。首次运行请先创建 `live_output/` 并赋权：  
> `mkdir -p live_output && chmod -R 777 live_output`

---

## 6. 配置要点

### 6.1 `qi.yaml`（主配置）
```yaml
exchange:
  name: okx
  simulated: false
risk:
  risk_pct: 0.007
  dd_limit: 0.08
execution:
  mode: autoexec
  prate: 0.12
portfolio:
  instruments:
    - { inst: BTC-USDT-SWAP, tf: 5m, risk_share: 1.0 }
paths:
  calendar: calendar.yaml
  live_dir: live_output
```
- 合法性由 Pydantic 校验（`qi doctor` 会给出具体字段错误）。
- **热加载文件**（无须重启）：`live_output/weights.json`、`cooling.json`、`thresholds.json`、`alloc.json`、`risk_overrides.json`。

### 6.2 `calendar.yaml`
- 配置交易窗口/静默日/特例；与 `PerformanceGuard`、`EventGuard` 协同。

### 6.3 监控与告警
- 启动指标服务：`qi metrics` 或多服务 compose 中的 `metrics`。  
- Grafana 面板：`qi grafana-export` 生成示例 JSON。  
- Prometheus 告警：`qi prom-rules` 生成 `prometheus/alerts.yml`。

---

## 7. 验收（Go/No-Go）清单
- `qi doctor` 通过；`preflight.json` 的 `ok: true`。
- 日志文件持续增长：`live_output/execlog.csv`、`trades_*.csv`、`equity*.csv`。
- 指标可访问：`curl localhost:9000/metrics`（应含 `qi_` 前缀指标）。
- 撤单比长期不超 3；回测/实盘归因为正向或可控。

---

## 8. 常见问题（Troubleshooting）
- **无成交/卡单**：看 `execlog.csv` 的 `PLACE/CANCEL`；必要时改 `exec_mode=pov` 或降低 `prate`。  
- **风控频繁拦截**：查看 `risk.log`、校验 `calendar.yaml` 与 `thresholds.json`。  
- **资金费/基差缺失**：检查网络连通与 `fetch_okx_funding_basis.py`；确认交易所 API 正常。  
- **时区混乱**：统一 `TZ=Asia/Tokyo`；容器与宿主一致。

---

## 9. 安全与合规
- `.env` 仅本机保存，不入库；生产用 Docker/K8s Secret。  
- 容器资源限制可通过 compose 配置（CPU/内存上限）。  
- 开启 `QI_JSON_LOGS=1` 便于合规审计和集中日志。

---

## 10. 升级/回滚
- 升级：替换解压目录 → `docker compose build --no-cache && docker compose up -d`。  
- 回滚：换回旧目录 → 同步构建启动即可；`live_output/` 可复用。

---

## 11. 一键体验
```bash
./bootstrap.sh   # 本机：安装 + 预检 + 启动
```


### v26 新服务
- push: 私有推送监听
- kpi: KPI 守护
- autotune: 自适应执行写控制

## 启动引导（统一入口）
- 统一脚本：`scripts/bootstrap.sh [auto|local|docker]`（默认 auto）
  - 旧的 `bootstrap_local.sh` / `bootstrap_docker.sh` 只是薄包装，均转发到 `bootstrap.sh`。
- 健康检查：`qi check`（聚合 `preflight` + `doctor`）。
