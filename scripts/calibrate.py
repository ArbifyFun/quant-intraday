#!/usr/bin/env python3
import argparse, os, json, numpy as np, pandas as pd
from quant_intraday.backtest.engine import Backtester
from quant_intraday.utils.time_windows import parse_time_windows
from quant_intraday.utils.risk import RiskParams

def parse_scale_outs(s):
    out=[]; 
    if s:
        for part in s.split(","):
            rr,p=part.split(":"); out.append((float(rr), float(p)))
    return tuple(out)

def walk_forward(df, strategy="auto", folds=4, grid=None, tz="UTC", windows="ALL"):
    if grid is None:
        grid={"risk":[0.004,0.005,0.006,0.007],"daily_loss":[0.015,0.02,0.025],"scale_outs":["1.0:0.5,1.5:0.25","1.2:0.33,1.8:0.33"],"trail":[0.8,1.0,1.2]}
    n=len(df); seg=n//(folds+1); results=[]
    for risk in grid["risk"]:
        for dl in grid["daily_loss"]:
            for so in grid["scale_outs"]:
                for trail in grid["trail"]:
                    rp=RiskParams(risk_pct=risk, daily_loss_limit_pct=dl, scale_out=parse_scale_outs(so), breakeven_rr=1.0, trail_atr_mult=trail)
                    scores=[]
                    for f in range(folds):
                        train=df.iloc[: seg*(f+1)]; test=df.iloc[ seg*(f+1) : seg*(f+2) ]
                        bt=Backtester(strategy=strategy, risk=rp, tz=tz, time_windows=None if windows=="ALL" else parse_time_windows(windows))
                        res2=bt.backtest(test, equity0=10_000.0); sharpe=res2["summary"]["sharpe"]; mdd=res2["summary"]["max_drawdown"]; score=sharpe - max(0.0, -mdd)
                        scores.append(score)
                    results.append(dict(risk=risk, daily_loss=dl, scale_outs=so, trail=trail, score=float(np.mean(scores))))
    results=sorted(results, key=lambda x:x["score"], reverse=True); return results

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--csv", required=True); p.add_argument("--inst", required=True); p.add_argument("--tz", default="UTC"); p.add_argument("--windows", default="ALL"); p.add_argument("--folds", default=4, type=int); a=p.parse_args()
    df=pd.read_csv(a.csv); 
    if "dt" in df.columns: df.index=pd.to_datetime(df["dt"], utc=True); df=df[["open","high","low","close","volume"]]
    else: ts=pd.to_datetime(df["timestamp"], utc=True, unit="ms"); df.index=ts; df=df[["open","high","low","close","volume"]]
    res=walk_forward(df, strategy="auto", folds=a.folds, tz=a.tz, windows=a.windows); best=res[0]; os.makedirs("calib", exist_ok=True)
    path=os.path.join("calib", a.inst.replace("/","-")+".json"); open(path,"w",encoding="utf-8").write(json.dumps(best, ensure_ascii=False, indent=2)); print("Best:", best, "=> saved", path)
