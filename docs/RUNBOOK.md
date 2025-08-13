# 运行手册（Runbook）

## 0. 术语
- trader：实盘主进程（`qi run`）。
- push：OKX 私有推送监听（`qi push`）。
- kpi：执行 KPI 守护进程（`qi kpi`）。
- autotune：自适应执行（`scripts/exec_autotune.py`）。
- metrics：Prometheus exporter（`qi metrics`）。

## 1. 启停与日常巡检
### Docker 多服务（推荐）
```bash
docker compose -f docker-compose.multi.yml up -d --build
docker compose ps
docker compose logs -f trader
curl -s localhost:9000/metrics | head   # 指标在线
open http://localhost:8080              # Web 面板
```
### 本地命令行
```bash
pip install -e .
qi doctor
qi run --cfg qi.yaml          # 实盘组合
qi push & qi kpi & qi metrics # 另起终端
```

## 2. 发布/升级/回滚
- **升级**：替换解压目录 → `docker compose build --no-cache && docker compose up -d`
- **回滚**：切回旧目录 → 同上；`live_output/` 可复用。
- **变更前**：`qi doctor` 通过；留存当前 `live_output/` 备份。

## 3. 现场故障排查（SOP）
| 症状 | 快速检查 | 解决方案 |
|---|---|---|
| 无成交、日志停更 | `docker compose ps; logs -f trader`；`:9000/metrics` 是否缺失 | 重启容器；检查 `.env` 与网络；`qi doctor` |
| 撤单比飙高 | Web 面板 KPI（cancel_ratio）；回放曲线 | 降低 `prate`→ Web「自适应」开；或在 `control.json.autotune` 手动设定 |
| 订单排队太深 | 订单级回放 `qpos_est` 高 | 切 `exec_mode=pov` 或 `optimizer`，缩小 `prate` |
| 当日亏损触发 | Web「账户风控」显示红线 | 查 `equity.csv` + 回放细节；必要时 `一键清仓` |
| WS 断连频繁 | `push` 日志；本地网络 | 增大重连间隔；检查代理/防火墙 |
| 面板访问 401 | 未设置/不匹配 `QI_WEB_TOKEN/Basic` | 修正 `.env` 或放到内网/VPN |

## 4. 数据文件
- `live_output/execlog.csv`：执行日志（PLACE/EXEC_START/FILL/CANCEL…）
- `live_output/trades_*.csv`：成交归档
- `live_output/equity*.csv`：权益快照
- `live_output/exec_kpis.json`：近 1h KPI（kpi 守护写入）
- `live_output/control.json`：控制/风控/自适应配置（**热加载**）
- `live_output/thresholds.json`、`weights.json`、`cooling.json`、`alloc.json`、`risk_overrides.json`：热参数

## 5. 紧急操作
- **一键清仓**：Web 面板 →「持仓&挂单」→ 执行；或 `python scripts/panic_flatten.py --dry` 先演练。  
- **全局暂停**：Web 面板 →「暂停 N 分钟」；或 `control.json` 写 `{"paused": true}`。

## 6. 备份与保留
- 保留 `live_output/`（含日志与参数），按日打包；敏感信息不入库。

## 7. 值班交接清单
- Web 面板 KPI 正常（fill_rate ≥ 0.35；cancel_ratio ≤ 3）。
- 报表：当日 PnL、最大 DD、成交/撤单数。 
- 风控阈值：`day_loss_limit_*` 是否启用；`per_inst_risk_cap_usd` 是否合理。
