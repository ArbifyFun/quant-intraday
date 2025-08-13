#!/usr/bin/env python3
"""
Calibrate impact lambda per instrument per session bucket (UTC hour buckets).
Buckets: ASIA[0-7], EU[7-13], US[13-22], OFF[22-24).
Input: attrib/positions_*.csv (from attr_pnl_v2.py)
Output: models/impact_lambda_buckets.json
"""
import os, glob, json, pandas as pd, numpy as np

def session_bucket(dt):
    h = int(pd.to_datetime(dt, utc=True).hour)
    if 0 <= h < 7: return "ASIA"
    if 7 <= h < 13: return "EU"
    if 13 <= h < 22: return "US"
    return "OFF"

def main(attrib_dir="attrib", out_path="models/impact_lambda_buckets.json"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    files=sorted(glob.glob(os.path.join(attrib_dir, "positions_*.csv")))
    if not files:
        print("no attrib files"); json.dump({}, open(out_path,"w")); return
    df=pd.read_csv(files[-1])
    if df.empty:
        json.dump({}, open(out_path,"w")); return
    df["entry_ts"]=pd.to_datetime(df["entry_ts"], utc=True, errors="coerce")
    df["bucket"]=df["entry_ts"].map(session_bucket)
    res={}
    for (inst,bkt), g in df.groupby(["inst","bucket"]):
        g=g.dropna(subset=["exec_cost_entry","qty"])
        if len(g)<5: continue
        x=g["qty"].astype(float).values.reshape(-1,1)
        y=(g["exec_cost_entry"]/g["qty"].replace(0,np.nan)).astype(float).fillna(0).values
        import numpy as np
        X=np.hstack([x, np.ones_like(x)]); lam=1e-6
        k = np.linalg.inv(X.T@X + lam*np.eye(2)) @ (X.T @ y)
        slope=float(k[0])
        if slope<0: slope=0.0
        res.setdefault(inst, {})[bkt]=slope
    with open(out_path,"w",encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("wrote", out_path, res)

if __name__=="__main__":
    main()
