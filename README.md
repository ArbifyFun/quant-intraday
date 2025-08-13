# Quant Intraday Toolkit (v26_20a patched)

This is a production-ready **crypto intraday trading toolkit** targeting BTC/ETH/SOL on OKX (REST + WebSocket),
with **portfolio orchestrator**, **strategy router**, **risk engine**, **OKX demo/live support**, and a **FastAPI Web UI**.

This patch consolidates your v26_20a code and fixes:
- OKX REST signing & timestamp drift (50112) handling
- WebSocket URL selection for demo/live + optional proxies
- `qi http-test` guaranteed (alias registered)
- `python-socks` added (WS SOCKS proxy support)
- Better `bootstrap.sh` (creates & activates venv, installs extras)
- Completed Web UI static/templates mounting
- Packaging exclusions, `.gitignore`, Docker notes

### Prerequisites

This toolkit is designed to use the official [TA‑Lib](https://mrjbq7.github.io/ta-lib/) C extension for technical analysis.  All indicator calculations assume that `TA‑Lib` is available in your Python environment.  For completeness and to enable limited backtesting in constrained environments (e.g. CI pipelines), a minimal pure‑Python fallback implementation lives in `quant_intraday/utils/talib_fallback.py`; however, **this fallback is intended only for development or testing** and may produce slightly different results.  In a production deployment you **should install the official `TA‑Lib` library** (see [installation instructions](https://mrjbq7.github.io/ta-lib/install.html)).  When `TA‑Lib` is present, the fallback is never used.

## Quickstart (macOS/Linux)

推荐使用统一的启动脚本 `scripts/bootstrap.sh` 进行一键安装和自检：

```bash
git clone <your-repo>
cd quant_intraday_toolkit_v26_20a
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh    # 自动选择 docker 或本地模式
```

脚本将在首次执行时创建 `.env`（如果不存在）、安装依赖并运行 `qi preflight` 与 `qi doctor`。若您希望显式指定模式，可传递 `local` 或 `docker` 参数。安装完成后，您可以手动激活虚拟环境并启动 Web UI 或组合交易：

```bash
source .venv/bin/activate     # 如在本地安装模式
qi web --host 0.0.0.0 --port 8080
qi run --cfg qi.yaml          # 启动组合实盘/模拟
```

更多 CLI 命令与参数说明详见 [docs/CLI.md](docs/CLI.md)。脚本工具的介绍在 [docs/SCRIPTS.md](docs/SCRIPTS.md)。

## Environment (.env)

```
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_API_PASSPHRASE=...
OKX_ACCOUNT=trade
OKX_SIMULATED=1                # 1 = demo/sandbox; unset or 0 = live
# Proxy (optional)
QI_PROXY_MODE=explicit         # off|env|explicit
QI_HTTP_PROXY=http://127.0.0.1:7890
QI_HTTPS_PROXY=http://127.0.0.1:7890
QI_WS_PROXY=socks5://127.0.0.1:1080
# Misc
QI_DEBUG_HTTP=1
QI_WEB_TOKEN=change-me
QI_LOG_DIR=live_output
TZ=Asia/Tokyo
```

## CLI

```
qi check          # run preflight then doctor; writes preflight.json and prints a summary
qi doctor         # validate qi.yaml and run preflight; exits non‑zero on failure
qi module-info    # print loaded module paths and Bot attribute flags (debugging aid)
qi kpi            # export execution KPIs from execlog.csv to JSON (runs daemon)
qi http-test      # REST sanity; prints status & body of /account/balance
qi run            # run portfolio from qi.yaml
qi backtest --csv your.csv --strategy auto --inst BTC-USDT-SWAP
qi web            # serve FastAPI Web UI

有关项目中大量辅助脚本的分类与用途说明，请参考 [docs/SCRIPTS.md](docs/SCRIPTS.md)。该文档按“运行与部署”“调参与自适应”“报告与监控”等类别对 `scripts/` 目录下的工具进行了详细梳理。借助这些脚本，可以定制自动调参、归因报告生成、执行回放、对账、Prometheus 指标导出等功能。
```

## Docker

```bash
# Build
docker build -t qi:latest .
# Run Web UI
docker run --rm -p 8080:8080 --env-file .env -v $PWD/live_output:/app/live_output qi:latest qi web --host 0.0.0.0 --port 8080
```

## Notes

- **Demo vs Live** is controlled by `OKX_SIMULATED`. Demo uses OKX *demo* REST base and WS addresses, with header `x-simulated-trading: 1`.
- If mainland access blocks OKX, set `QI_PROXY_MODE=explicit` and set the three proxy envs.
- The Web UI requires `uvicorn` & `jinja2` (bundled); static assets live in `quant_intraday/webui/static/`.

---

Below is the original README content for reference:

---
# Quant Intraday (Crypto, TA-Lib) — v7

**策略池**：`trend / pullback / range / vwap / ib / squeeze / fbr / obi / mi / auto(调度器)`  
**交易所**：OKX（REST 下单 / 策略单 TP/SL / 改单），公共 & 私有 WS。  
**风控**：单笔风险 / 日亏熔断 / 组合风控（跨品种）/ 事件黑名单。  
**执行**：分批止盈、保本、ATR 追踪，订单簿滑点估计（books5）。  
**观测**：Prometheus 指标、OOS 看板、TG/飞书告警。  
**回测**：t+1 成交、SL/TP 命中检测、手续费&滑点建模、分批/保本/追踪。

## 快速开始
```bash
pip install -r requirements.txt
```

### 拉历史（OKX V5）
```bash
python scripts/fetch_okx_csv.py --inst BTC-USDT-SWAP --bar 5m --out btc_swap_5m.csv
```

### 回测 + 报告
```bash
python scripts/run_backtest.py --strategy auto --csv btc_swap_5m.csv \
  --risk 0.006 --daily-loss 0.02 --scale-outs "1.0:0.5,1.5:0.25" \
  --breakeven-rr 1.0 --trail-atr 1.0 --fee-bps 6 --tick-size 0.1 --slip-ticks 2
# 输出：backtest_output/equity.csv, trades.csv, report.html
```

### 实盘（建议先 dry-run，再小额）
```bash
export OKX_API_KEY=... ; export OKX_API_SECRET=... ; export OKX_API_PASSPHRASE=... ; export OKX_ACCOUNT=trade
export TELEGRAM_BOT_TOKEN=... ; export TELEGRAM_CHAT_ID=...  # 可选
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live false \
  --time-windows "21:00-02:00" --use-private true \
  --scale-legs "50,30,20" --trailing-be-rr 1.0 --trailing-atr-mult 1.0
# 上线（小额）
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true \
  --risk 0.006 --time-windows "21:00-02:00" --use-private true \
  --scale-legs "50,30,20" --trailing-be-rr 1.0 --trailing-atr-mult 1.0
```

### Supervisor（BTC/ETH/SOL）
```bash
python scripts/supervisor.py --config live_manifest.yaml
```

### 指标/看板/告警
```bash
# Prometheus Exporter（默认 8008）
python scripts/metrics_exporter.py --port 8008

# 实盘 OOS 看板（HTML）
python scripts/oos_dashboard.py

# TG 图片推送
python scripts/telegram_report.py

# 飞书卡片
python scripts/feishu_card.py
```

## v7 新增
- **事件风控**：`events_blackout.yaml` 自动禁入（CPI/FOMC 等）。
- **订单簿滑点估计**：books5 → VWAP impact。
- **REST 错误熔断**：错误过多 → 冷却。
- **指标增强**：追踪改价成功/失败、风控拦截；附 Grafana JSON。

> 重要提醒：我不保证“稳赚”。请严格走：**回测 → 干跑 → 小额灰度 → 放量**。日亏上限建议 ≤2%，组合 ≤3%。


## v8 更新
- **成本模型（每品种）**：`utils/cost_model.py` + `costs.yaml`，自动读取 `tickSz/lotSz`，可按品种覆盖 `taker/maker bps` 与**进场激进度**（entry_aggr_ticks）。
- **盘口感知下单价**：从 `books5` 获取盘口，按 `entry_aggr_ticks` 在最优档基础上微抬/压 1–2 tick，**尽量被动成交**（或轻度吃单）。
- **自适应策略权重**：`scripts/weight_adaptor.py` 根据最近 live trades 粗估胜率，输出 `live_output/weights.json`，调度器按权重优先级路由（权重≤0 即禁用）。
- **成交对账 & 执行报告**：`scripts/reconcile.py` 拉取 OKX fills，对齐本地意图，计算**执行滑点**分布，输出 recon/。
  
### 自适应权重
```bash
# 每小时跑一次（cron）
python scripts/weight_adaptor.py
# Router 会自动热加载 live_output/weights.json
```

### 成交对账
```bash
export OKX_API_KEY=... ; export OKX_API_SECRET=... ; export OKX_API_PASSPHRASE=... ; export OKX_ACCOUNT=trade
python scripts/reconcile.py
# 输出 recon/reconciled_YYYYMMDD.csv 与 recon/daily_exec_report.html
```

### 成本文件
编辑 `costs.yaml`，覆盖你的费率 / tick / lot / 进场 aggressiveness。未配置时自动回退到交易所合约元数据。


## v9 更新
- **动态拆单器（Slicer）**：`--exec-mode slicer`，按 `--prate/--max-slices/--slice-timeout` 逐笔挂单，结合盘口定价，尽量被动成交（或轻微吃单）。
- **质量过滤 & 自适应冷却**：低 ATR/Volume 分位时自动减频；可配 `--min-atr-pct`、`--min-vol-pct`、`--adaptive-cool`。
- **成交生命周期 & 归因**：`scripts/attr_pnl.py` 将 fills 聚合成回合（round-trip），与本地意图对齐，给出 **执行成本（进场滑点+费）与 Alpha** 的拆分。

### 例子：Slicer 实盘（小额）
```bash
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true \
  --exec-mode slicer --prate 0.1 --max-slices 8 --slice-timeout 3 \
  --min-atr-pct 0.2 --min-vol-pct 0.3 --adaptive-cool true
```

### 归因日报
```bash
export OKX_API_KEY=... ; export OKX_API_SECRET=... ; export OKX_API_PASSPHRASE=... ; export OKX_ACCOUNT=trade
python scripts/attr_pnl.py
# 输出 attrib/positions_YYYYMMDD.csv 与 attrib/attribution_report.html
```


## v10 更新
- **执行优化器（Cancel/Repost）**：`--exec-mode optimizer`，基于盘口定价，按 `--opt-step-ticks / --opt-max-reposts / --slice-timeout` 循环**撤单重挂**；私有 WS 可判定是否已满额成交；最后一轮可选择**跨价成交**（`--opt-cross-last`）。
- **指标扩展**：读取 `live_output/execlog.csv`，曝光 `qi_exec_place / qi_exec_cancel / qi_exec_place_fail / qi_exec_cancel_fail / qi_exec_fill_all`。
- **严谨归因 v2**：基于 fills 的**回合**，按意图推断 entry/exit 的目标价，拆分**入场执行成本**、**出场执行成本**与 **Alpha**，并按**品种/策略**出汇总表。

### 例子：Optimizer 实盘（小额）
```bash
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true \
  --exec-mode optimizer --slice-timeout 3 --opt-step-ticks 1 --opt-max-reposts 6 --opt-cross-last true
```

### 归因 v2 报表
```bash
python scripts/attr_pnl_v2.py
# 输出 attrib/positions_YYYYMMDD.csv 与 attrib/attribution_report.html
```


## v11 更新
- **POV 执行器**：`--exec-mode pov` 小额多笔，目标参与率（maker 优先，必要时 1 tick 轻吃）；基于 books5 的队列/中价变化自适应。
- **退出触发标记**：私有 WS 回调识别 `take-profit/stop-loss` 成交，记录到 `exits.log`，Exporter 输出 `qi_exit_tp/qi_exit_sl/qi_exit_manual`。
- **动态分配（实盘自适应）**：`scripts/rebalance.py` 读取 attribution，生成 `alloc.json`（品种风险倍数）与 `weights.json`（策略权重）——Bot 热加载，无需重启。

### 自适应调仓
```bash
# 每 1h 重算一次
python scripts/rebalance.py
# Bot 将按 alloc.json 调整 risk_pct 倍数，按 weights.json 调整策略优先级
```

### POV 执行示例
```bash
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true \
  --exec-mode pov --prate 0.12 --slice-timeout 2
```

> 说明：v11 的 POV/Optimizer 都是“工程可用”的版本，不做过度复杂的队列建模。若需要更激进的队列占位/撤单频控、盘口事件驱动（LOB 级别），可在 v12 再上一层。


## v12 更新
- **交易日历（时区/节假日/UTC特例）**：`calendar.yaml` + `TradeCalendar`，配合原有 TimeWindows 与 EventGuard，形成更严格的入场门禁。
- **LOB 事件驱动执行器**：`--exec-mode lob`，基于 spread/imbalance/队列的事件**撤单重挂**，带**最小驻留**与**每分钟撤单上限**节流。
- **回测执行模型**：`--exec-mode simple|kyle` 与 `--kyle-lambda`，把执行冲击纳入回测，降低回测↔实盘风格偏差。
- **指标增强**：`qi_cancel_ratio`（撤单比）、`qi_queue_depth`（Maker/Cross 代理）。

### 日历用法
```bash
vi calendar.yaml   # 修改时区/静默日/时段/特例
export QI_CALENDAR_FILE=calendar.yaml
```

### LOB 执行示例
```bash
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true \
  --exec-mode lob --slice-timeout 3 \
  --min-atr-pct 0.2 --min-vol-pct 0.3
```

### 回测带执行冲击
```bash
python scripts/run_backtest.py --strategy auto --csv btc_swap_5m.csv \
  --exec-mode kyle --kyle-lambda 0.5e-2
```


## v13 更新
- **最优队列位置估计（启发式）**：`engine/queue_tracker.py`，在 POV/LOB 下单时记录 best-queue，并持续估计**队列位置占比**（0~1）。
- **冲击 λ 标定**：`scripts/calibrate_lambda.py` 读取 attribution v2 输出，按品种回归得到 λ，写入 `models/impact_lambda.json`；回测优先使用该 λ。
- **执行回放**：`scripts/exec_replay.py` 对齐 `execlog.csv` 与 fills，输出 HTML 时间线，辅助排查执行器行为与滑点来源。

### 标定 & 回测
```bash
python scripts/attr_pnl_v2.py             # 先生成 attribution
python scripts/calibrate_lambda.py        # 写 models/impact_lambda.json
export QI_LAMBDA_FILE=models/impact_lambda.json
python scripts/run_backtest.py --strategy auto --csv btc_swap_5m.csv --inst BTC-USDT-SWAP --exec-mode kyle
```

> 说明：队列位置是启发式估计（OKX 不直接提供排队位次），用于**择价与执行决策的倾向参考**，不是绝对真值。若你需要更精准的“自己订单在队列中的位次”，需要撮合层更细粒度的事件或自建撮合模拟器。


## v14 更新
- **分桶 λ（会话时段）**：`scripts/calibrate_lambda_buckets.py` 产出 `impact_lambda_buckets.json`（ASIA/EU/US/OFF）；回测按入场时间段优先读取分桶 λ。
- **AutoExecutor（执行策略选择器）**：`--exec-mode autoexec`，基于**价差（tick）**与**队列位置估计**，在 Optimizer / POV / LOB 间自适应切换。
- **策略级冷却（自适应）**：`scripts/autopilot.py` 从归因 v2 的 per-strategy alpha 推出 `weights.json`（0–2）与 `cooling.json`（秒），Bot 热加载并在入场前强制执行。

### 用法速览
```bash
# 1) 归因 → λ 标定（分桶）
python scripts/attr_pnl_v2.py
python scripts/calibrate_lambda_buckets.py
export QI_LAMBDA_BUCKETS_FILE=models/impact_lambda_buckets.json

# 2) 自适应调度（权重+冷却）
python scripts/autopilot.py   # 写 live_output/{weights,cooling}.json

# 3) 实盘自动执行器
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true --exec-mode autoexec
```


## v15 更新
- **多维冲击 λ 标定**：`scripts/calibrate_lambda_nd.py`（会话 × 波动三分位 × 成交量三分位），输出 `models/impact_lambda_nd.json`；回测优先读取 ND λ → 分桶 λ → 全局 λ。
- **AutoExecutor++（取消预算感知）**：在撤单预算不足时自动降级到 `POV`，避免触发交易所限频；仍按队列位置/价差动态切换。
- **订单生命周期日志**：`EXEC_START/EXEC_END` 记录执行模式/耗时，方便排查。
- **AutoML++**：`scripts/autopilot_plus.py` 在生成权重/冷却之外，按近 1 天 OOS 表现自动写 `thresholds.json`（动态调 `min_atr_pct/min_vol_pct`）。
- **LiveBot**：热加载 `thresholds.json` 并覆盖入场门槛；新增撤单计数器（1 分钟滚动）供自动执行器使用。

### 日常调度建议（crontab）
```bash
# 每小时：权重/冷却/阈值
python scripts/autopilot_plus.py

# 每日：归因 & λ 标定（分桶 & 多维）
python scripts/attr_pnl_v2.py
python scripts/calibrate_lambda_buckets.py
python scripts/calibrate_lambda_nd.py
export QI_LAMBDA_BUCKETS_FILE=models/impact_lambda_buckets.json
export QI_LAMBDA_ND_FILE=models/impact_lambda_nd.json
```


## v16 更新
- **资金费 / 基差 单腿信号**：新增 `FundingBias`、`BasisTilt`（同所 perp-季度基差），注入 Router 优先级靠前，可与技术信号联动。
- **波动率目标（VolTarget）**：基于 ATR% 动态缩放 `risk_pct`，波动大则降杠杆、波动小则加杠杆（带上下限）。
- **性能守门（PerformanceGuard）**：滚动统计 TP/SL 与连续亏损，劣化时自动冷却/暂停入场。
- **历史数据脚本**：`fetch_okx_funding_basis.py` 拉取 funding & 基差历史，便于回测做外生特征。
- **Walk-Forward（简版）**：`wfo_grid.py` 用时间剔除（purged）切分做参数网格，输出每折最佳。

### 实盘建议
- 开启 `--exec-mode autoexec`；资金费/基差信号将作为**方向倾向**，不会强行逆势抄底。  
- VolTarget 默认日波动目标 2%，上下限 `0.6x~1.6x`，按需在 `vol_target.py` 调整。  
- PerformanceGuard 默认容忍 **3 连亏**或 **TP 比例 < 35%**，触发冷却 5 分钟。

### 历史 Funding/基差
```bash
python scripts/fetch_okx_funding_basis.py --inst BTC-USDT-SWAP --fut BTC-USDT-240927 --out btc_fb.csv
```


## v17 更新
- **多品种实盘编排**：`portfolio.yaml` + `scripts/run_multi_live.py`，一条命令同时跑 BTC/ETH/SOL（或自定义），按 `risk_share` 划分全局风险预算。
- **Kelly 风格风险缩放**：`scripts/kelly_scaler.py` 根据最近实盘的胜率/赔率（简化估计）写 `risk_overrides.json`，Bot 热加载并叠加到 sizing。
- **全局风险熔断**：`GlobalRiskGuard` 监控组合 `equity*.csv` 的**日内回撤**，越线触发暂停（并发 webhook 通知）。
- **Webhook 通知**：`utils/notifier.py`，设置 `QI_WEBHOOK_URL` 即可在**风控拦截/熔断/下单失败**等要点出钉。
- **容器化部署**：`Dockerfile` + `docker-compose.yml` + `.env.example`，一条命令起服务。

### 组合实盘（推荐）
```bash
cp .env.example .env            # 填好 OKX 密钥
docker compose up -d --build    # 默认读取 portfolio.yaml 跑 BTC/ETH/SOL
# 或本机起：
python scripts/run_multi_live.py --cfg portfolio.yaml --risk 0.007 --dd 0.08
```

### Kelly 风险缩放（每小时一次）
```bash
python scripts/kelly_scaler.py   # 写 live_output/risk_overrides.json
```

> 注：`kelly_scaler.py` 的胜率/赔率估计是**保守简化版**；若你提供完整 fills 与平仓回放，我们可以用 v10/v13 的归因明细做**精确胜率/赔率**估计，Kelly 将更稳。



# 运维与上线指北（v18）

## 快速起飞
```bash
pip install -r requirements.txt
python scripts/preflight.py            # 必跑，检查环境/连通性/权限
# 单品种（建议先 BTC）
python scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true --exec-mode autoexec
# 组合（BTC/ETH/SOL）
python scripts/run_multi_live.py --cfg portfolio.yaml --risk 0.007 --dd 0.08
```

## 配置一览
- `.env.example`：OKX 密钥、模拟盘开关 `OKX_SIMULATED=1`、日志路径 `QI_LOG_DIR`、Webhook。  
- `portfolio.yaml`：多品种清单与 `risk_share`。  
- `calendar.yaml`：时区/交易窗口/静默日/特例。  
- `live_output/`（热加载）：`weights.json`、`alloc.json`、`cooling.json`、`thresholds.json`、`risk_overrides.json`。

## 实盘前清单（Go/No-Go）
- [ ] `python scripts/preflight.py` 显示 `ok: true`。  
- [ ] `.env` 已填密钥；若走模拟盘，设置 `OKX_SIMULATED=1`（或 `OKX_ACCOUNT=paper` 兼容）。  
- [ ] 小额干跑 `--live false` 验证路由/执行器日志流转。  
- [ ] `scripts/metrics_exporter.py` 起在 9000 端口（或容器健康检查）。  
- [ ] `autopilot_plus.py`、`kelly_scaler.py`、`rebalance.py` 加入 cron。  
- [ ] `portfolio.yaml` 已按资金规模设置 `risk_share`。  
- [ ] `calendar.yaml` 按你时区/作息确认。

## 故障与回滚
- 一键暂停：在 `live_output/thresholds.json` 临时写入高阈值（如 `{"min_atr_pct":0.9,"min_vol_pct":0.9}`）→ 30s 内生效。  
- 组合熔断：`scripts/run_multi_live.py` 的 DD 限制触发后会通知 Webhook 并暂停新入场。  
- 回滚版本：替换运行目录的 zip 解包内容，保留 `live_output` 目录即可。



## 一体化 CLI（v19）
安装（本地开发或容器内部）
```bash
pip install -e .
qi version
```

最常用命令
```bash
qi preflight                 # 上线前自检
qi run --cfg qi.yaml         # 读取主配置一键起组合
qi live --inst BTC-USDT-SWAP --tf 5m --strategy auto --exec-mode autoexec  # 单品种
qi multi --cfg portfolio.yaml
qi backtest --csv data/btc_swap_5m.csv --inst BTC-USDT-SWAP --exec-mode kyle --kyle-lambda 0.005
qi autopilot                 # 权重/冷却/阈值 + Kelly 风险缩放
qi metrics                   # 暴露指标端口 :9000
qi replay                    # 生成执行回放 HTML
qi fetch-fb --inst BTC-USDT-SWAP --fut BTC-USDT-240927 --out fb.csv
```

配置入口
- `qi.yaml` 作为主配置；兼容 `portfolio.yaml`、`calendar.yaml`、`live_output/*` 热加载文件。
- 环境变量与 `.env` 仍生效（OKX 密钥、OKX_SIMULATED、QI_LOG_DIR、QI_WEBHOOK_URL）。


## v19.1 小更新
- 新增多服务 Compose：`docker-compose.multi.yml`（trader + autopilot + metrics）。
- 支持 `python -m quant_intraday` 启动。
- `bootstrap.sh`：一键安装 + 预检 + 启动（本机快速体验）。

### 多服务起法
```bash
docker compose -f docker-compose.multi.yml up -d --build
```


更多使用说明见 docs/QUICKSTART.md、docs/CLI.md、docs/ALERTS.md。


部署细节见：docs/DEPLOYMENT.md


Web 面板使用说明见：docs/WEBUI.md


更多文档：docs/QUICKSTART.md、docs/DEPLOYMENT.md、docs/WEBUI.md、docs/RUNBOOK.md、docs/CONFIG.md、docs/SECURITY.md、docs/CHANGELOG.md


## 代理与网络
三档：
- `QI_PROXY_MODE=off|env|explicit`
- REST 代理：`QI_HTTP_PROXY` / `QI_HTTPS_PROXY`
- WebSocket 代理（可选 SOCKS5）：`QI_WS_PROXY`，未设置时回退到 `QI_HTTPS_PROXY`/`QI_HTTP_PROXY`

示例：
```
QI_PROXY_MODE=explicit
QI_HTTP_PROXY=http://127.0.0.1:7890
QI_HTTPS_PROXY=http://127.0.0.1:7890
QI_WS_PROXY=socks5://127.0.0.1:7891
```
SIM 环境：
```
OKX_SIMULATED=1
OKX_DEMO_BROKER_ID=9999
```



### .env 自动加载
从 v26.17 起，`qi` 命令与预检会在启动时自动加载当前工作目录下的 `.env`（不会覆盖已导出的环境变量）。



### 环境加载策略（v26.18）
- 启动时会用 `find_dotenv(usecwd=True)` 向上查找最近的 `.env`，自动加载（不会覆盖已导出的环境变量）。
- 你可以用 `qi env` 查看当前生效的环境变量（秘钥字段做了脱敏）。


