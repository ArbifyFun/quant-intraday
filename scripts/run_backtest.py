#!/usr/bin/env python3
import argparse, os, numpy as np, pandas as pd
from quant_intraday.backtest.engine import Backtester
from quant_intraday.utils.time_windows import parse_time_windows
from quant_intraday.utils.risk import RiskParams
from datetime import datetime, timedelta, timezone

def gen_synth(bars=4000, seed=42):
    rng=np.random.default_rng(seed)
    dt0=datetime(2024,1,1,tzinfo=timezone.utc)
    times=[dt0 + timedelta(minutes=5*i) for i in range(bars)]
    drift=rng.normal(0.0,0.03,bars); noise=rng.normal(0,0.5,bars)
    x=np.cumsum(drift+noise); base=20000 + x + 50*np.sin(np.linspace(0, 15, bars))
    high=base + rng.random(bars)*5; low=base - rng.random(bars)*5
    open_=base + rng.normal(0, 0.5, bars); close=base + rng.normal(0, 0.5, bars)
    vol= rng.lognormal(mean=8.5, sigma=0.2, size=bars)
    df=pd.DataFrame({"open":open_,"high":high,"low":low,"close":close,"volume":vol}, index=pd.to_datetime(times)); df.index.name="dt"; return df

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--csv", default=None)
    p.add_argument("--strategy", default="auto", choices=["auto","trend","vwap","ib","obi","mi","squeeze","pullback","range","fbr"])
    p.add_argument("--bars", default=6000, type=int); p.add_argument("--seed", default=42, type=int)
    p.add_argument("--equity", default=10000.0, type=float)
    p.add_argument("--risk", default=0.007, type=float); p.add_argument("--daily-loss", default=0.02, type=float)
    p.add_argument("--scale-outs", default="1.0:0.5,1.5:0.25"); p.add_argument("--breakeven-rr", default=1.0, type=float)
    p.add_argument("--trail-atr", default=1.0, type=float)
    p.add_argument("--max-bars", default=48, type=int); p.add_argument("--tz", default="UTC")
    p.add_argument("--time-windows", default=os.getenv("TRADE_WINDOWS","ALL"))
    p.add_argument("--fee-bps", default=5.0, type=float); p.add_argument("--tick-size", default=0.1, type=float); p.add_argument("--slip-ticks", default=1, type=int)
    p.add_argument("--exec-mode", default="simple", choices=["simple","kyle"])
    p.add_argument("--kyle-lambda", default=0.0, type=float)
    a=p.parse_args()
    if a.csv and os.path.exists(a.csv):
        df=pd.read_csv(a.csv); 
        if "dt" in df.columns: df.index=pd.to_datetime(df["dt"], utc=True); df=df[["open","high","low","close","volume"]]
        else: ts=pd.to_datetime(df["timestamp"], utc=True, unit="ms"); df.index=ts; df=df[["open","high","low","close","volume"]]
    else:
        df=gen_synth(a.bars, a.seed)
    so=[]
    if a.scale_outs.strip():
        for part in a.scale_outs.split(","):
            rr,pct=part.split(":"); so.append((float(rr), float(pct)))
    rp=RiskParams(risk_pct=a.risk, daily_loss_limit_pct=a.daily_loss, scale_out=tuple(so), breakeven_rr=a.breakeven_rr, trail_atr_mult=a.trail_atr)
    tw=None if a.time_windows=="ALL" else parse_time_windows(a.time_windows)
    bt=Backtester(strategy=a.strategy, risk=rp, max_bars_in_trade=a.max_bars, time_windows=tw, tz=a.tz, fee_bps=a.fee_bps, tick_size=a.tick_size, slippage_ticks=a.slip_ticks, exec_mode=a.exec_mode, kyle_lambda=a.kyle_lambda, inst_id=a.inst) if hasattr(a,"inst") else Backtester(strategy=a.strategy, risk=rp, max_bars_in_trade=a.max_bars, time_windows=tw, tz=a.tz, fee_bps=a.fee_bps, tick_size=a.tick_size, slippage_ticks=a.slip_ticks, exec_mode=a.exec_mode, kyle_lambda=a.kyle_lambda)
    res=bt.backtest(df, equity0=a.equity); summary=res["summary"]
    print("==== Backtest Summary ===="); 
    for k,v in summary.items(): print(f"{k:>15s}: {v:.6f}" if isinstance(v,float) else f"{k:>15s}: {v}")
    outdir="backtest_output"; os.makedirs(outdir, exist_ok=True)
    res["equity"].to_csv(os.path.join(outdir,"equity.csv"))
    import csv
    with open(os.path.join(outdir,"trades.csv"),"w",newline="",encoding="utf-8") as f:
        w=csv.writer(f); w.writerow(["entry_time","exit_time","side","entry","exit","size","pnl","pnl_pct","bars","reason"])
        for t in res["trades"]:
            w.writerow([t.entry_time, t.exit_time, t.side, t.entry, t.exit, t.size, t.pnl, t.pnl_pct, t.bars, t.reason])
    from scripts.make_report import main as make_report; make_report(outdir)
    print("Saved to backtest_output/ (report.html)")
