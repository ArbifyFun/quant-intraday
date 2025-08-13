#!/usr/bin/env python3
import argparse, os, asyncio
from quant_intraday.engine.live_bot import Bot, RunConfig, load_env
from quant_intraday.exchange.okx_client import OKXClient

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--inst", required=True); p.add_argument("--tf", default="5m")
    p.add_argument("--strategy", default="auto")
    p.add_argument("--live", default="false")
    p.add_argument("--risk", default=0.007, type=float)
    p.add_argument("--mode", default="cross")
    p.add_argument("--time-windows", default=os.getenv("TRADE_WINDOWS","ALL"))
    p.add_argument("--cooldown", default=20, type=int)
    p.add_argument("--scale-legs", default="50,30,20")
    p.add_argument("--exec-mode", default="simple", choices=["simple","slicer","optimizer","pov","lob","autoexec"])
    p.add_argument("--prate", default=0.1, type=float)
    p.add_argument("--max-slices", default=8, type=int)
    p.add_argument("--slice-timeout", default=3, type=int)
    p.add_argument("--opt-step-ticks", default=1, type=int)
    p.add_argument("--opt-max-reposts", default=5, type=int)
    p.add_argument("--opt-cross-last", default="true")
    p.add_argument("--min-atr-pct", default=0.20, type=float)
    p.add_argument("--min-vol-pct", default=0.30, type=float)
    p.add_argument("--adaptive-cool", default="true")
    p.add_argument("--use-private", default="false")
    p.add_argument("--trailing-be-rr", default=1.0, type=float)
    p.add_argument("--trailing-atr-mult", default=1.0, type=float)
    args=p.parse_args()
    cfg=RunConfig(inst_id=args.inst, tf=args.tf, live=args.live.lower()=="true", risk_pct=args.risk, td_mode=args.mode,
                  strategy=args.strategy, time_windows=args.time_windows, cooldown_s=args.cooldown,
                  scale_legs=args.scale_legs, use_private=args.use_private.lower()=="true",
                  trailing_be_rr=args.trailing_be_rr, trailing_atr_mult=args.trailing_atr_mult,
                  exec_mode=args.exec_mode, prate=args.prate, max_slices=args.max_slices, slice_timeout_s=args.slice_timeout,
                  min_atr_pct=args.min_atr_pct, min_vol_pct=args.min_vol_pct, adaptive_cool=(args.adaptive_cool.lower()=="true"),
                  opt_step_ticks=args.opt_step_ticks, opt_max_reposts=args.opt_max_reposts, opt_cross_last=(args.opt_cross_last.lower()=="true"))
    client=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    asyncio.run(Bot(cfg, client).run())
