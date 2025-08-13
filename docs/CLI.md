# CLI 参考

```
qi version
qi preflight
qi doctor
qi run --cfg qi.yaml
qi live --inst BTC-USDT-SWAP --tf 5m --strategy auto --exec-mode autoexec
qi multi --cfg portfolio.yaml --risk 0.007 --dd 0.08
qi backtest --csv data/btc_swap_5m.csv --inst BTC-USDT-SWAP --exec-mode kyle --kyle-lambda 0.005
qi autopilot
qi metrics
qi replay
qi fetch-fb --inst BTC-USDT-SWAP --fut BTC-USDT-240927 --out fb.csv
qi grafana-export --out grafana/dashboard_quant_intraday.json
qi prom-rules --out prometheus/alerts.yml
qi completions --shell bash|zsh|fish
```
