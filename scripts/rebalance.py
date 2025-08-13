#!/usr/bin/env python3
"""
Compute per-instrument risk multipliers and strategy weights from attribution/live trades.
- Reads attrib/positions_*.csv if available; fallback to live_output/trades_*.csv proxy.
- Outputs: live_output/alloc.json (inst->multiplier), live_output/weights.json (strategy->weight).
"""
import os, json, glob, pandas as pd, numpy as np
from collections import defaultdict

def load_attrib(attrib_dir="attrib"):
    files=sorted(glob.glob(os.path.join(attrib_dir, "positions_*.csv")))
    if not files: return None
    df=pd.read_csv(files[-1])
    return df

def main(live_dir="live_output", attrib_dir="attrib"):
    os.makedirs(live_dir, exist_ok=True)
    alloc_path=os.path.join(live_dir, "alloc.json")
    weights_path=os.path.join(live_dir, "weights.json")
    df=load_attrib(attrib_dir)
    if df is None or df.empty:
        # Fallback: neutral allocation
        json.dump({}, open(alloc_path,"w")); 
        if not os.path.exists(weights_path): json.dump({}, open(weights_path,"w"))
        print("No attrib; wrote neutral alloc/weights"); return
    # per instrument alpha
    per_inst = df.groupby("inst")["alpha"].sum().to_dict()
    # normalize to [0.8, 1.2]
    if per_inst:
        vals=list(per_inst.values()); lo=min(vals); hi=max(vals); rng=(hi-lo) if hi!=lo else 1.0
        alloc={k: float(0.8 + 0.4*( (v-lo)/rng )) for k,v in per_inst.items()}
        json.dump(alloc, open(alloc_path,"w"), ensure_ascii=False, indent=2)
    # per strategy alpha -> weights [0,2], baseline 1
    if "strategy" in df.columns:
        per_strat = df.groupby("strategy")["alpha"].sum().to_dict()
        vals=list(per_strat.values()); lo=min(vals); hi=max(vals); rng=(hi-lo) if hi!=lo else 1.0
        weights={k: float(0.4 + 1.6*((v-lo)/rng)) for k,v in per_strat.items()}
        json.dump(weights, open(weights_path,"w"), ensure_ascii=False, indent=2)
    print("Wrote", alloc_path, "and", weights_path)

if __name__=="__main__":
    main()
