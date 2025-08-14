# 脚本工具参考（scripts/）

本项目在 `scripts/` 目录下提供了大量实用工具，用于参数调优、归因分析、监控运维以及运行回测/实盘。这些脚本并非必需，但根据需要可以单独运行，配合主程序提升策略效果与运维效率。

## 运行与部署

| 脚本 | 作用与使用场景 |
| --- | --- |
| **bootstrap.sh** | 一键引导脚本，根据环境自动选择本地或 Docker 部署，创建虚拟环境、安装依赖、生成 `.env`，并运行 `qi doctor` 检查。建议初次安装时运行 `scripts/bootstrap.sh auto`。 |
| **bootstrap_local.sh** / **bootstrap_docker.sh** | `bootstrap.sh` 的瘦包装，分别强制本地或 Docker 部署。 |
| **run_backtest.py** | 运行回测并生成 `backtest_output/` 报告。可指定 CSV 数据、策略名称、风险参数、手续费模型等。 |
| **run_live.py** | 单品种实盘入口，支持指定品种、周期、策略、执行模式和风险参数等，可设置 `--live true` 进行真实下单。 |
| **run_multi_live.py** | 组合实盘入口，读取 `qi.yaml` 或 `portfolio.yaml` 批量启动多品种交易。 |
| **supervisor.py** | 通过清单文件管理多个 `run_live.py` 进程，实现多账户或多实例的统一控制。 |
| **preflight.py** (根目录) | 连接 OKX 并检查密钥有效性、时间同步、网络连通性等，生成 `preflight.json` 诊断。 |
| **healthcheck.py** | 简易健康检查，查看执行日志文件更新时间，用于 Docker HEALTHCHECK。 |

## 参数调优与自适应

| 脚本 | 作用与使用场景 |
| --- | --- |
| **autopilot.py** / **autopilot_plus.py** | 根据过去的归因数据计算各策略权重、冷却时间以及风险阈值，生成 `weights.json`、`cooling.json`、`thresholds.json` 供调度器热加载。可定时运行以实现策略自适应。 |
| **calibrate.py** | 在指定历史数据上进行滚动窗口交叉验证，网格搜索最佳风险和追踪参数，输出最优参数 JSON。 |
| **calibrate_lambda.py** / **calibrate_lambda_buckets.py** / **calibrate_lambda_nd.py** | 根据成交记录估算价格冲击模型中每个品种或时间段的 λ（lambda）值，结果保存在 `models/impact_lambda*`。 |
| **weight_adaptor.py** | 根据近期实盘胜率调整策略权重，输出 `weights.json`。适合按小时或日常 cron 调用。 |
| **kelly_scaler.py** | 使用 Kelly 公式根据近期盈利率计算每个品种的风险上限，生成 `risk_overrides.json`。 |
| **exec_autotune.py** | 分析执行 KPI（撤单率、填单率）自动调整下单激进度 `prate` 和执行模式，更新 `control.json`。 |
| **panic_flatten.py** | 紧急平仓脚本，支持实盘和平仓模拟模式，立即撤销所有挂单并平掉仓位。 |

## 报告与监控

| 脚本 | 作用与使用场景 |
| --- | --- |
| **attr_pnl.py** / **attr_pnl_v2.py** | 将实盘成交与本地交易意图对齐，按策略和品种拆分总收益为执行成本与 Alpha，生成归因报告（CSV/HTML）。v2 版本支持按入场和出场分离执行成本。 |
| **reconcile.py** | 类似于归因脚本，用于每日对账。拉取 OKX fills 与本地日志比对，输出每日执行报告和对账文件。 |
| **make_report.py** | 对回测结果生成 HTML 报告，包括净值曲线、最大回撤、按小时胜率等图表。 |
| **exec_replay.py** | 基于执行日志和成交记录，重构订单生命周期并生成交互式回放 HTML，便于复盘单次交易全过程。 |
| **terminal_dashboard.py** | 基于 Rich 的终端实时看板，彩色展示权益、执行指标、仓位、信号与成交，支持自定义刷新间隔与成交行数，时间戳为 UTC。 |
| **oos_dashboard.py** | 创建组合实盘的实时看板，将收益、回撤等指标绘制为 HTML 图表，适合独立部署。 |
| **metrics_exporter.py** | 解析实时生成的日志文件并导出 Prometheus 指标，如委托数、撤单数、填单率、策略 PnL 等。可部署为守护进程供 Grafana 监控。 |
| **telegram_report.py** / **feishu_card.py** | 定时抓取实盘或回测数据并推送到 Telegram 或飞书，支持图片形式和卡片形式。 |
| **exec_kpi_daemon.py** | 读取 `live_output/execlog.csv`，统计委托和成交 KPI 并定期写入 JSON，可配合 `exec_autotune.py` 动态调整执行参数。 |

## 数据抓取与分析

| 脚本 | 作用与使用场景 |
| --- | --- |
| **fetch_okx_csv.py** / **fetch_okx_funding_basis.py** | 从 OKX API 获取指定品种的历史 OHLCV 数据和资金费率/基差信息，保存为 CSV 文件，用于回测或研究。 |
| **wfo_grid.py** | 生成 walk‑forward 优化的网格参数组合并批量跑回测，汇总每组结果，用于多参数模型的粗略筛选。 |
| **attr_pnl.py** / **reconcile.py** | 归因和对账脚本（见上）。 |
| **exec_replay.py** | 执行回放（见上）。 |

## 其它辅助脚本

| 脚本 | 作用与使用场景 |
| --- | --- |
| **enter.sh** / **activate.sh** | 帮助用户进入虚拟环境，加载依赖。`activate.sh` 在新终端中激活 venv 并启动 shell，`enter.sh` 可用于进入容器内的 Bash 环境。 |
| **smoke.py** | 简单的 smoke 测试入口，用于快速运行单元测试检查核心组件是否正常工作。 |

上述脚本通过合理组合可满足回测、实盘、调优、监控和报告的一揽子需求。建议根据实际需求编写定时任务（Cron/K8s Jobs）或使用 Docker Compose 中的多服务配置自动化运行。