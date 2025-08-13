# Web 面板（v20）

最小可用 Web 面板（FastAPI + Jinja）。支持：
- 暂停/恢复（写 `live_output/control.json`；Bot 热加载）。
- 修改阈值（`thresholds.json` 热加载）。
- 查看最近 `trades_*.csv` 和 `execlog.csv` tail。
- 简单鉴权：Bearer `$QI_WEB_TOKEN`（可选）。

## 启动

Docker 多服务：
```bash
docker compose -f docker-compose.multi.yml up -d --build
# 面板： http://localhost:8080
# 如设置了 QI_WEB_TOKEN： curl -H "Authorization: Bearer $QI_WEB_TOKEN" ...
```

本地命令行：
```bash
pip install -e .
QI_WEB_TOKEN=yourtoken qi web --host 0.0.0.0 --port 8080
```

## 安全建议
- 务必设置 `QI_WEB_TOKEN`；或将服务置于内网/VPN 后。  
- 需要更强控制可加 Nginx 反代 + HTTP Basic/OIDC；这是 v21 的增强方向。

## 扩展计划（可选）
- 实时图表（uPlot/Plotly）接入 `equity.csv` 与 /metrics。  
- 阈值以外的热参数编辑（weights/cooling/alloc/risk_overrides）。  
- 交易回放页面（复用 `exec_replay.py` 产物）。


## v21 更新
- 实时权益图（SSE，每2秒）。
- 在线 JSON 编辑（weights/cooling/alloc/risk_overrides/control）。
- 可选 Basic Auth（`QI_WEB_BASIC_USER/QI_WEB_BASIC_PASS`）。


## v22 更新
- 实时指标（从 Prometheus exporter 读取 snapshot）。
- 执行回放概览：每分钟 PLACE/CANCEL/FILL 计数图。
- 策略开关：control.json 的 disable_strategies 热编辑。


## v23 更新
- 账户风控：`control.json` 支持 `day_loss_limit_usd/day_loss_limit_pct/per_inst_risk_cap_usd`；引擎强约束禁止新入场。
- 回放细节：/api/replay_detail 从 OKX 拉 K 线，叠加 execlog/trades 事件点，支持 inst/tf/lookback 参数。


## v24 更新
- 面板新增“持仓/挂单”视图与“一键清仓”按钮（调用 `scripts/panic_flatten.py`）。
- `panic_flatten.py`：撤单 + 市价 reduce-only 全品种/指定品种平仓。
- 自动检测执行会话（EXEC_START/EXEC_END），一键拉取对应窗口的价格+事件回放。


## v25 更新
- 订单级回放：输入 clOrdId/ordId 查询 execlog 轨迹（含 qpos_est、reason 等扩展字段）。
- LOB 订阅（books5）用于估算下单时队列位置（qpos_est）。
- 增强 execlog：统一写入器，自动扩展 CSV 列，避免 schema 变化导致写入失败。


## v26 更新
- OKX 私有推送（orders）→ execlog 写 FILL/CANCEL/PARTFILL/AMEND。
- KPI 守护进程 → exec_kpis.json；面板与 Prometheus 指标读取。
- 自适应执行（Autotune）→ 根据 KPI 自动写 control.json 覆盖 prate/exec_mode（Bot 热读）。
