# 告警配置

- 生成示例规则：`qi prom-rules` → `prometheus/alerts.yml`
- 导出示例面板：`qi grafana-export` → `grafana/dashboard_quant_intraday.json`

关键指标：
- `qi_equity`、`qi_pnl`：权益与收益。
- `qi_cancel_ratio`：撤单比。
- `qi_queue_pos_est`：队列位置估计。
- `qi_exec_fill_all`：成交事件计数。

建议告警：
- 15 分钟无指标（容器可能挂或 WS 断）。
- 撤单比 > 3 持续 10 分钟（可能触发限频）。
- 1 日内 DD > 8%。
