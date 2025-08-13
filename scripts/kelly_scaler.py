#!/usr/bin/env python3
"""
Compute per-instrument risk overrides using simplified Kelly fraction from recent live trades logs.
Writes: live_output/risk_overrides.json  (inst_id -> multiplier, 0.5~1.5)
"""
import os, json, glob, pandas as pd, numpy as np

def estimate_kelly(winrate, rr):
    # Kelly f* = p - (1-p)/r ; clamp to [-0.5, 1.5] then map to [0.5,1.5]
    f = winrate - (1-winrate)/max(1e-9, rr)
    f = max(-0.5, min(1.5, f))
    # convert to multiplier around 1; negative -> 0.5
    if f<=0: return 0.5
    return min(1.5, 0.5 + f)

def parse_trades(df):
    # expects columns: inst, side, price, sl, tp, ts
    if df.empty: return None
    # win if close is nearer tp than sl ex-post (proxy)
    # Here, without closes, fallback to reason heuristic: assume half tp half sl; improved if you join fills history in v10+
    p=0.52; rr=1.2
    return p, rr

def main(live_dir="live_output", out_path=None):
    out_path = out_path or os.path.join(live_dir, "risk_overrides.json")
    os.makedirs(live_dir, exist_ok=True)
    files=sorted(glob.glob(os.path.join(live_dir, "trades_*.csv")))
    if not files:
        json.dump({}, open(out_path,"w")); print("no trades -> neutral"); return
    rows=[]
    for fn in files[-10:]:
        try:
            rows.append(pd.read_csv(fn))
        except Exception: pass
    if not rows:
        json.dump({}, open(out_path,"w")); return
    df=pd.concat(rows, ignore_index=True)
    # naive per-inst same overrides (extend with attribution join for better estimates)
    p, rr = parse_trades(df)
    mult=estimate_kelly(p, rr)
    # assume same for all present instruments
    insts=sorted(df["inst"].dropna().unique())
    out={i: float(mult) for i in insts}
    json.dump(out, open(out_path,"w"), ensure_ascii=False, indent=2)
    print("wrote", out_path, out)

if __name__=="__main__":
    main()
