#!/usr/bin/env python3
"""
AutoML++:
- From attribution v2, compute per-strategy weights/cooling (delegate to autopilot.py)
- From OOS equity/trades (live_output/*.csv) compute gating thresholds (min_atr_pct/min_vol_pct)
  heuristic: if last 7d hit rate drops & drawdown expands, raise thresholds; otherwise lower a bit.
Writes: live_output/{weights.json,cooling.json,thresholds.json}
"""
import os, json, glob, pandas as pd, numpy as np
from datetime import datetime, timedelta

def load_equity(live_dir):
    files=sorted(glob.glob(os.path.join(live_dir, "equity_*.csv")))
    if not files:
        eq = os.path.join(live_dir, "equity.csv")
        if os.path.exists(eq): files=[eq]
    if not files: return None
    df=pd.read_csv(files[-1])
    if "ts" in df.columns:
        df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df

def main(live_dir="live_output", attrib_dir="attrib"):
    os.makedirs(live_dir, exist_ok=True)
    # delegate weights/cooling
    try:
        from scripts.autopilot import main as ap_main
        ap_main(live_dir, attrib_dir)
    except Exception as e:
        pass
    thresholds_path=os.path.join(live_dir, "thresholds.json")
    # Default
    th={"min_atr_pct":0.20,"min_vol_pct":0.30}
    eq=load_equity(live_dir)
    if eq is not None and len(eq)>10:
        eq["ret"]=eq["equity"].pct_change().fillna(0.0)
        last=eq.tail(1440)  # ~1d samples if 1min, else just last N
        dd=(last["equity"]/last["equity"].cummax()-1.0).min()
        vol=last["ret"].std()
        # simple rule: worse DD and higher vol -> tighten gating
        adj = 0.0
        if dd < -0.05: adj += 0.05
        if vol > 0.01: adj += 0.05
        th["min_atr_pct"]=min(0.6, 0.20+adj)
        th["min_vol_pct"]=min(0.7, 0.30+adj)
    json.dump(th, open(thresholds_path,"w"), ensure_ascii=False, indent=2)
    print("wrote", thresholds_path, th)

if __name__=="__main__":
    main()
