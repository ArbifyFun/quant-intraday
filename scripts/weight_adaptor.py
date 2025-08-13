#!/usr/bin/env python3
"""
Update strategy weights based on recent live trades (winrate by strategy keyword).
Output live_output/weights.json; weights in [0, 2] (1.0 baseline).
"""
import os, json, pandas as pd
from collections import defaultdict

def parse_strategy(reason: str) -> str:
    if not isinstance(reason, str) or not reason: return "unknown"
    key = reason.split("|")[0].strip()
    # key may be 'trend', 'ib', etc. Ensure in known set
    return key

def main(live_dir="live_output", lookback_trades=200):
    weights_path=os.path.join(live_dir, "weights.json")
    # collect trades
    all_rows=[]
    for fn in os.listdir(live_dir):
        if fn.startswith("trades_") and fn.endswith(".csv"):
            df=pd.read_csv(os.path.join(live_dir, fn))
            all_rows.append(df.tail(lookback_trades))
    if not all_rows:
        print("no trades yet"); return
    df=pd.concat(all_rows, ignore_index=True)
    df["strategy"]=df["reason"].map(parse_strategy)
    # assume pnl can be approximated by tp/sl proximity? We don't have realized pnl here.
    # Using proxy: if tp closer than sl at entry -> tentative win bias. Fallback: neutral 0.5
    import numpy as np
    prox=(df["tp"].astype(float)-df["price"].astype(float)).abs() - (df["price"].astype(float)-df["sl"].astype(float)).abs()
    win_est=(prox>0).astype(float)  # tp距更远 => 0, sl距更远 => 1; simplistic
    res=win_est.groupby(df["strategy"]).mean().to_dict()
    # map to weights: 0.4~1.6 linear
    weights={k: max(0.0, min(2.0, 0.4 + 1.2*float(v))) for k,v in res.items()}
    with open(weights_path, "w", encoding="utf-8") as f:
        json.dump(weights, f, ensure_ascii=False, indent=2)
    print("Saved weights to", weights_path, weights)

if __name__=="__main__":
    main()
