#!/usr/bin/env python3
"""
Calibrate per-instrument impact lambda using attribution v2 outputs:
lambda ~= slope of (exec_cost_entry / qty) vs (qty / ADV) or vs absolute qty.
Outputs: models/impact_lambda.json
"""
import os, glob, json, pandas as pd, numpy as np

def main(attrib_dir="attrib", out_path="models/impact_lambda.json"):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    files=sorted(glob.glob(os.path.join(attrib_dir, "positions_*.csv")))
    if not files:
        print("no attrib files"); json.dump({}, open(out_path,"w")); return
    df=pd.read_csv(files[-1])
    if df.empty:
        json.dump({}, open(out_path,"w")); return
    # use per-instrument regression of exec_cost_entry/qty ~ k * qty
    res={}
    for inst,g in df.groupby("inst"):
        g=g.dropna(subset=["exec_cost_entry","qty"])
        if len(g)<5: continue
        x=g["qty"].astype(float).values.reshape(-1,1)
        y=(g["exec_cost_entry"]/g["qty"].replace(0,np.nan)).astype(float).fillna(0).values
        # simple ridge-like closed form with small L2
        import numpy as np
        X=np.hstack([x, np.ones_like(x)]); lam=1e-6
        k = np.linalg.inv(X.T@X + lam*np.eye(2)) @ (X.T @ y)
        slope=float(k[0]); 
        if slope<0: slope=0.0
        res[inst]=slope
    with open(out_path,"w",encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("wrote", out_path, res)

if __name__=="__main__":
    main()
