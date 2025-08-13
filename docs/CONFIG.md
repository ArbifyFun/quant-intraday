# 配置说明（CONFIG）

## 1. `qi.yaml`（主配置）
```yaml
exchange: { name: okx, simulated: false }
risk: { risk_pct: 0.007, dd_limit: 0.08, vol_target_daily: 0.02 }
execution: { mode: autoexec, prate: 0.12, slice_timeout: 3 }
portfolio:
  instruments:
    - { inst: BTC-USDT-SWAP, tf: 5m, risk_share: 1.0 }
paths: { calendar: calendar.yaml, portfolio: portfolio.yaml, live_dir: live_output }
```
- 字段均有 Pydantic 校验（`qi doctor` 会指出非法字段/范围）。

## 2. `.env`（环境变量）
- `OKX_API_KEY/OKX_API_SECRET/OKX_API_PASSPHRASE`（必填）  
- `OKX_SIMULATED=1`：模拟盘（强烈建议先跑 24–48h）  
- `OKX_ACCOUNT=trade`：账户标识  
- `QI_WEB_TOKEN` 或 `QI_WEB_BASIC_USER/PASS`：Web 面板鉴权  
- `TZ=Asia/Tokyo`：建议统一时区

## 3. `control.json`（热加载控制/风控/自适应）
```json
{
  "paused": false,
  "pause_until": 0,
  "disable_strategies": ["funding","basis"],
  "day_loss_limit_usd": 500,
  "day_loss_limit_pct": 0.08,
  "per_inst_risk_cap_usd": { "BTC-USDT-SWAP": 200, "ETH-USDT-SWAP": 150 },
  "autotune": {
    "enabled": true,
    "min_fill_rate": 0.35,
    "max_cancel_ratio": 3.0,
    "bounds_prate": [0.06, 0.20],
    "prate_by_inst": { "BTC-USDT-SWAP": 0.12 },
    "exec_mode_by_inst": { "BTC-USDT-SWAP": "autoexec" }
  }
}
```

## 4. `calendar.yaml`
- 配置可交易时段/禁入窗口/节假日等；与性能/事件守门协同。
