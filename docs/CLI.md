# CLI 参考

```
qi version                                 # 查看当前版本
qi preflight                               # 网络连通 & 账号预检，写入 live_output/preflight.json
qi doctor                                  # 校验 qi.yaml、.env 等配置
qi check                                   # 预检 + doctor 二合一
qi run --cfg qi.yaml                       # 按组合配置启动实盘/模拟
qi live --inst BTC-USDT-SWAP ...           # 单品种运行，支持 --tf/--strategy 等参数
qi multi --cfg portfolio.yaml ...          # 按 portfolio.yaml 启动多品种
qi backtest --csv data.csv ...             # CSV 回测入口
qi autopilot                               # 执行权重/冷却/阈值自调
qi metrics                                 # 暴露 Prometheus 指标服务（默认 :9000）
qi replay                                  # 重建执行时间线，生成 HTML 回放
qi kpi                                     # 从 execlog 生成执行 KPI JSON
qi module-info                             # 调试工具，打印模块导入路径和 Bot 属性
qi http-test                               # REST 测试，打印 /account/balance 响应
qi fetch-fb --inst BTC-USDT-SWAP ...       # 抓取永续资金费率与基差数据
qi grafana-export --out grafana/dashboard.json  # 导出 Grafana 示例面板
qi prom-rules --out prometheus/alerts.yml  # 导出 Prometheus 告警规则
qi web --host 0.0.0.0 --port 8080         # 启动 FastAPI Web UI
qi completions --shell bash|zsh|fish       # 生成 Shell 自动补全脚本
```

更多脚本工具请参阅 [SCRIPTS.md](SCRIPTS.md)。
