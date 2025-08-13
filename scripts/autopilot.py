#!/usr/bin/env python3
"""
Autopilot: from attribution v2 (alpha by strategy), derive strategy weights [0,2]
and cooldown seconds per strategy (longer cooldown for negative alpha).
Outputs: live_output/weights.json, live_output/cooling.json
"""
import os, json, glob, pandas as pd, numpy as np

def main(live_dir="live_output", attrib_dir="attrib"):
    os.makedirs(live_dir, exist_ok=True)
    weights_path=os.path.join(live_dir, "weights.json")
    cooling_path=os.path.join(live_dir, "cooling.json")
    files=sorted(glob.glob(os.path.join(attrib_dir, "positions_*.csv")))
    if not files:
        print("no attrib -> neutral"); 
        if not os.path.exists(weights_path): json.dump({}, open(weights_path,"w"))
        if not os.path.exists(cooling_path): json.dump({}, open(cooling_path,"w"))
        return
    df=pd.read_csv(files[-1])
    if df.empty or "strategy" not in df.columns:
        print("attrib empty -> neutral"); 
        if not os.path.exists(weights_path): json.dump({}, open(weights_path,"w"))
        if not os.path.exists(cooling_path): json.dump({}, open(cooling_path,"w"))
        return
    agg=df.groupby("strategy")["alpha"].sum().sort_values()
    vals=agg.values
    lo, hi = (vals[0], vals[-1]) if len(vals)>0 else (0.0, 0.0)
    rng = (hi-lo) if hi!=lo else 1.0
    weights={k: float(0.4 + 1.6*((v-lo)/rng)) for k,v in agg.to_dict().items()}
    # cooldown: map alpha -> [30s, 1800s]
    def map_cool(a):
        # negative -> long cool, positive -> short
        if rng==0: return 300
        ratio=(a-lo)/rng
        secs=int(30 + (1.0-ratio)*1770)  # 30~1800
        return max(10, min(3600, secs))
    cooling={k: map_cool(v) for k,v in agg.to_dict().items()}
    json.dump(weights, open(weights_path,"w"), ensure_ascii=False, indent=2)
    json.dump(cooling, open(cooling_path,"w"), ensure_ascii=False, indent=2)
    print("wrote", weights_path, "and", cooling_path)

if __name__=="__main__":
    main()
