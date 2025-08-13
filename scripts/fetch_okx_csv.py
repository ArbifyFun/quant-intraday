#!/usr/bin/env python3
import httpx, argparse, time, pandas as pd
BASE="https://www.okx.com"
def fetch(inst_id: str, bar: str="5m", limit: int=1000, max_pages: int=200):
    path="/api/v5/market/history-candles"; rows=[]; before=None; cli=httpx.Client(base_url=BASE, timeout=10)
    for _ in range(max_pages):
        params={"instId":inst_id,"bar":bar,"limit":str(limit)}
        if before: params["before"]=str(before)
        r=cli.get(path, params=params); r.raise_for_status(); data=r.json().get("data", [])
        if not data: break
        for k in data:
            ts=int(k[0]); o,h,l,c = map(float,k[1:5]); v=float(k[5] if len(k)>5 else (k[7] if len(k)>7 else 0.0))
            rows.append((ts,o,h,l,c,v))
        before=data[-1][0]; time.sleep(0.1)
    rows=sorted(set(rows), key=lambda x:x[0])
    df=pd.DataFrame(rows, columns=["timestamp","open","high","low","close","volume"])
    df["dt"]=pd.to_datetime(df["timestamp"], unit="ms", utc=True); df=df[["dt","open","high","low","close","volume"]]
    return df
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--inst", required=True); p.add_argument("--bar", default="5m"); p.add_argument("--out", default=None)
    a=p.parse_args(); df=fetch(a.inst, a.bar); out=a.out or (a.inst.replace("/","-")+"_"+a.bar+".csv"); df.to_csv(out, index=False); print("Saved", out)
