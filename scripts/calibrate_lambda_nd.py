#!/usr/bin/env python3
"""
Calibrate impact lambda by multi-dim buckets:
- session (ASIA/EU/US/OFF by UTC hour)
- volatility quantile (rolling ATR14 over 500 bars at entry; 3 bins: low/med/high)
- volume quantile (rolling vol over 500 bars; 3 bins)
Output: models/impact_lambda_nd.json: {inst: {session: {volq: {volm: lambda}}}}
"""
import os, glob, json, pandas as pd, numpy as np

def session_bucket(dt):
    h = int(pd.to_datetime(dt, utc=True).hour)
    if 0 <= h < 7: return "ASIA"
    if 7 <= h < 13: return "EU"
    if 13 <= h < 22: return "US"
    return "OFF"

def q3(x):
    # map to 0,1,2 tertiles
    try:
        q1, q2 = x.quantile(1/3), x.quantile(2/3)
        return np.select([x<=q1, x<=q2], [0,1], default=2)
    except Exception:
        return pd.Series([1]*len(x), index=x.index)

def main(attrib_dir="attrib", out_path="models/impact_lambda_nd.json"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    files=sorted(glob.glob(os.path.join(attrib_dir, "positions_*.csv")))
    if not files:
        print("no attrib files"); json.dump({}, open(out_path,"w")); return
    df=pd.read_csv(files[-1])
    if df.empty:
        json.dump({}, open(out_path,"w")); return
    # need entry_ts for session; fall back to dt if missing
    tscol = "entry_ts" if "entry_ts" in df.columns else "dt"
    df[tscol]=pd.to_datetime(df[tscol], utc=True, errors="coerce")
    df["session"]=df[tscol].map(session_bucket)
    # proxy vol/volume at entry: rolling stats per instrument using available history columns if exist; fall back to qty
    if "avg_entry" in df.columns and "exit_px" in df.columns:
        # lacking raw bars, we approximate: use absolute return as vol proxy and qty as volm proxy
        ret = (df["exit_px"] - df["avg_entry"]).abs() / df["avg_entry"].replace(0,np.nan)
        df["volq"]=q3(ret.fillna(ret.median()))
    else:
        df["volq"]=1
    df["volm"]=q3(df["qty"].astype(float))
    res={}
    for (inst,sess,vq,vm), g in df.groupby(["inst","session","volq","volm"]):
        g=g.dropna(subset=["exec_cost_entry","qty"])
        if len(g)<6: 
            continue
        x=g["qty"].astype(float).values.reshape(-1,1)
        y=(g["exec_cost_entry"]/g["qty"].replace(0,np.nan)).astype(float).fillna(0).values
        X=np.hstack([x, np.ones_like(x)]); lam=1e-6
        k = np.linalg.inv(X.T@X + lam*np.eye(2)) @ (X.T @ y)
        slope=float(k[0]); slope=max(0.0, slope)
        res.setdefault(inst, {}).setdefault(str(sess), {}).setdefault(str(int(vq)), {})[str(int(vm))]=slope
    with open(out_path,"w",encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("wrote", out_path)

if __name__=="__main__":
    main()
