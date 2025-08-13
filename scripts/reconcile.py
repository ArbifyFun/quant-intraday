#!/usr/bin/env python3
"""
Pulls OKX fills and reconciles with local trade intents (live_output/trades_*.csv).
Outputs recon/reconciled_YYYYMMDD.csv and recon/daily_exec_report.html
"""
import os, httpx, json, pandas as pd, datetime as dt
from quant_intraday.exchange.okx_client import OKXClient

def load_intents(live_dir="live_output"):
    rows=[]
    for fn in os.listdir(live_dir):
        if fn.startswith("trades_") and fn.endswith(".csv"):
            df=pd.read_csv(os.path.join(live_dir, fn))
            rows.append(df)
    if not rows: return pd.DataFrame(columns=["ts","inst","side","price","sl","tp","size","reason"])
    df=pd.concat(rows, ignore_index=True)
    df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df

def fetch_fills(cli: OKXClient, inst_type="SWAP", limit=100):
    path="/api/v5/trade/fills-history"
    j=cli._get(path, params={"instType": inst_type, "limit": str(limit)})
    return pd.DataFrame(j.get("data", []))

def main(live_dir="live_output", out_dir="recon"):
    os.makedirs(out_dir, exist_ok=True)
    cli=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    intents=load_intents(live_dir)
    fills=fetch_fills(cli)
    if fills.empty:
        print("No fills data"); return
    fills["ts"]=pd.to_datetime(fills["ts"], unit="ms", utc=True)
    fills["side"]=fills["side"].str.upper()
    # left join intents within 5 minutes window
    intents=intents.sort_values("dt")
    out_rows=[]
    for _,f in fills.iterrows():
        inst=f.get("instId"); side=f.get("side").upper()
        ts=f.get("ts")
        subset=intents[(intents["inst"]==inst) & (intents["side"]==("LONG" if side=="BUY" else "SHORT")) & (abs((intents["dt"]-ts).dt.total_seconds())<=300)]
        intended_price=subset["price"].iloc[-1] if len(subset)>0 else None
        exec_px=float(f.get("fillPx", f.get("px", "0")))
        diff = None if intended_price is None else float(exec_px) - float(intended_price)
        out_rows.append({"dt":ts, "inst":inst, "side":side, "exec_px":exec_px, "intended_px":intended_price, "slippage":diff, "trade_id": f.get("tradeId")})
    recon=pd.DataFrame(out_rows).sort_values("dt")
    day=dt.datetime.utcnow().strftime("%Y%m%d")
    recon.to_csv(os.path.join(out_dir, f"reconciled_{day}.csv"), index=False)
    # html summary
    slip = recon["slippage"].dropna()
    mean = float(slip.mean()) if len(slip)>0 else 0.0
    p95  = float(slip.quantile(0.95)) if len(slip)>0 else 0.0
    html=f"<html><meta charset='utf-8'><body><h1>Daily Execution Report</h1><p>Mean slippage: {mean:.6f} | 95%: {p95:.6f} | n={len(slip)}</p>{recon.tail(100).to_html(index=False)}</body></html>"
    with open(os.path.join(out_dir, "daily_exec_report.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved recon to", out_dir)

if __name__=='__main__':
    main()
