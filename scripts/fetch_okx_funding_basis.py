#!/usr/bin/env python3
"""
Fetch OKX funding-rate history & same-exchange perp-vs-quarterly basis (approx) and save CSV.
"""
import os, httpx, pandas as pd, time

BASE="https://www.okx.com"

def fetch_funding(inst_id: str, limit=100):
    url=f"{BASE}/api/v5/public/funding-rate-history?instId={inst_id}&limit={limit}"
    j=httpx.get(url, timeout=10).json()
    rows=[]
    for d in j.get("data", []):
        ts=int(d["fundingTime"]); rate=float(d["fundingRate"])*3*365
        rows.append(dict(ts=ts, funding=rate))
    df=pd.DataFrame(rows).sort_values("ts")
    return df

def fetch_basis(inst_id: str, fut_id: str, limit=200):
    # proxy: use last prices snapshots (rough); for proper calc use bar joins
    urlp=f"{BASE}/api/v5/market/history-index-candles?instId={inst_id}&bar=1H&limit={limit}"
    urlf=f"{BASE}/api/v5/market/history-candles?instId={fut_id}&bar=1H&limit={limit}"
    jp=httpx.get(urlp, timeout=10).json(); jf=httpx.get(urlf, timeout=10).json()
    def parse(j):
        rows=[]
        for k in j.get("data", []):
            ts=int(k[0]); close=float(k[4])
            rows.append((ts, close))
        return rows
    p=parse(jp); f=parse(jf)
    dfp=pd.DataFrame(p, columns=["ts","mark"]).sort_values("ts")
    dff=pd.DataFrame(f, columns=["ts","last"]).sort_values("ts")
    df=dfp.merge(dff, on="ts", how="inner")
    df["basis_bps"]=(df["last"]/df["mark"]-1.0)*10000.0
    return df

def main(inst="BTC-USDT-SWAP", fut="BTC-USDT-240927", out="fb_history.csv"):
    df1=fetch_funding(inst)
    try:
        df2=fetch_basis(inst, fut)
        df=df1.merge(df2, on="ts", how="outer").sort_values("ts")
    except Exception:
        df=df1
    df.to_csv(out, index=False)
    print("saved", out, len(df))

if __name__=="__main__":
    main()
