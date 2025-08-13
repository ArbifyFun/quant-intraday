#!/usr/bin/env python3
"""
Execution replay: align execlog.csv with fills-history to rebuild a timeline.
Outputs replay/replay_YYYYMMDD.html
"""
import os, json, pandas as pd, datetime as dt
from quant_intraday.exchange.okx_client import OKXClient

def load_execlog(live_dir="live_output"):
    ex=os.path.join(live_dir, "execlog.csv")
    if not os.path.exists(ex):
        return pd.DataFrame(columns=["ts","evt","inst","side","pos","sz","px"])
    df=pd.read_csv(ex)
    df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df

def fetch_fills(cli, inst_type="SWAP", limit=1000):
    j=cli._get("/api/v5/trade/fills-history", params={"instType":inst_type,"limit":str(limit)})
    df=pd.DataFrame(j.get("data", []))
    if df.empty: return df
    df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["fillPx"]=df["fillPx"].astype(float)
    df["fillSz"]=df["fillSz"].astype(float)
    return df

def main(live_dir="live_output", out_dir="replay"):
    os.makedirs(out_dir, exist_ok=True)
    cli=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    exe=load_execlog(live_dir)
    fills=fetch_fills(cli)
    if fills.empty:
        print("no fills"); return
    html="<html><meta charset='utf-8'><body><h1>Execution Replay</h1>"
    html+=exe.tail(200).to_html(index=False)
    html+="<h2>Fills (tail)</h2>"+fills.tail(200).to_html(index=False)
    with open(os.path.join(out_dir, "replay_%s.html"%dt.datetime.utcnow().strftime("%Y%m%d")), "w", encoding="utf-8") as f:
        f.write(html)
    print("saved replay")

if __name__=="__main__":
    main()
