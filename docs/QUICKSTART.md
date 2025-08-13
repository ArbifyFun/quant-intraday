# 快速上手

以下步骤帮助您快速体验项目的基本功能，包括一键安装、本地运行和多服务部署。假设您已解压本仓库或通过 `git clone` 获取源码。

## 1. 一键安装

项目提供了统一的启动脚本 `scripts/bootstrap.sh`，可自动检测环境并选择本机安装或容器部署。执行以下命令即会在本机创建虚拟环境、安装依赖并初始化配置；若检测到 Docker 可用，则直接启动多服务栈：

```bash
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh    # auto 模式：优先使用 docker；若无则本地 venv
```

脚本将在当前目录生成 `.env`（若不存在）并提示您修改 OKX API 密钥。完成后会运行 `qi preflight` 与 `qi doctor` 进行自检。

如需手动运行，可指定模式：

```bash
./scripts/bootstrap.sh local    # 强制本地虚拟环境安装
./scripts/bootstrap.sh docker   # 强制启动 Docker 服务
```

## 2. 填写配置

1. **`.env`**：填入 `OKX_API_KEY/SECRET/PASSPHRASE`，并根据需要设置 `OKX_SIMULATED=1` 以启用模拟盘。其他代理、日志目录及时区配置也可以在此定义。
2. **`qi.yaml`**：修改品种列表、风险敞口、执行模式等参数。例如：

```yaml
exchange: { name: okx, simulated: true }
risk: { risk_pct: 0.007, dd_limit: 0.08 }
execution: { mode: autoexec, prate: 0.12 }
portfolio:
  instruments:
    - { inst: BTC-USDT-SWAP, tf: 5m, risk_share: 1.0 }
paths: { calendar: calendar.yaml, live_dir: live_output }
```

更多字段见 [CONFIG.md](CONFIG.md)。

## 3. 自检

在正式运行前，建议执行以下自检命令：

```bash
qi doctor          # 验证 qi.yaml 与环境变量
qi preflight       # 检查网络连通与账户余额，写入 live_output/preflight.json
```

二者可组合为 `qi check`（`qi check` 会先运行 preflight 再运行 doctor）。确保输出中的 `ok` 字段为 `true`。

## 4. 启动交易

通过 CLI 启动实盘或模拟交易：

```bash
qi run --cfg qi.yaml          # 从 qi.yaml 启动组合实盘
qi live --inst BTC-USDT-SWAP --tf 5m --strategy auto --exec-mode autoexec  # 单品种运行
```

运行时生成的日志、热加载文件（权重、冷却、阈值等）位于 `live_output/`。Web UI 可通过以下命令查看实时行情与订单：

```bash
qi web --host 0.0.0.0 --port 8080
```

浏览器访问 `http://localhost:8080` 并使用 `.env` 中设置的 `QI_WEB_TOKEN` 进行鉴权。

## 5. 多服务自动化

若想同时运行交易 Bot、自动调参及指标导出，可使用多服务组合：

```bash
docker compose -f docker-compose.multi.yml up -d --build
```

该配置包括：

- **trader**：组合交易主进程。
- **autopilot**：定时计算策略权重、阈值和冷却时间，写入 `live_output/`。
- **metrics**：暴露 Prometheus 指标（监听端口可在 compose 文件中调整）。

如仅需要简单部署，可使用 `docker-compose.yml` 单服务版本。

## 6. 后续步骤

- 按需查阅 [SCRIPTS.md](SCRIPTS.md) 了解各辅助脚本功能，例如回测报告、执行归因、风控调参等。
- 配置 Grafana 仪表和 Prometheus 告警规则请参考 [DEPLOYMENT.md](DEPLOYMENT.md) 中的示例和说明。
- 在切换到真实交易前，建议先在模拟盘运行 24–48 小时，并根据回测/归因报告调整策略参数。
