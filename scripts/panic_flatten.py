#!/usr/bin/env python3
"""
Panic flatten: cancel all pending orders and close all open positions (market reduce-only).
Usage: python scripts/panic_flatten.py [--inst BTC-USDT-SWAP] [--dry]
"""
import os, argparse, time
from quant_intraday.exchange.okx_client import OKXClient

def list_positions(cli, inst=None):
    j = cli._get("/api/v5/account/positions", {"instType":"SWAP", **({"instId":inst} if inst else {})})
    return j.get("data", [])

def list_pending(cli, inst=None):
    j = cli._get("/api/v5/trade/orders-pending", {"instId": inst} if inst else {})
    return j.get("data", [])

def cancel_all(cli, inst=None):
    pend = list_pending(cli, inst)
    for o in pend:
        try:
            cli.cancel_order(instId=o.get("instId"), ordId=o.get("ordId"))
            time.sleep(0.05)
        except Exception as e:
            print("cancel err:", e)

def close_all(cli, inst=None, tdMode="cross"):
    poss = list_positions(cli, inst)
    for p in poss:
        try:
            instId = p.get("instId"); posSide = p.get("posSide")
            sz = p.get("availPos") or p.get("pos") or "0"
            if float(sz) == 0: 
                continue
            side = "sell" if posSide=="long" else "buy"
            cli.place_order(instId=instId, tdMode=tdMode, side=side, posSide=posSide, ordType="market", sz=sz, reduceOnly="true", clOrdId=f"panic_{int(time.time())}")
            time.sleep(0.05)
        except Exception as e:
            print("close err:", e)

def main(inst=None, dry=False):
    cli = OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    if dry:
        print("DRY RUN. Pending:", list_pending(cli, inst)); print("Positions:", list_positions(cli, inst)); return
    cancel_all(cli, inst)
    close_all(cli, inst)
    print("panic flatten complete")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--inst", default=None)
    ap.add_argument("--dry", action="store_true")
    a=ap.parse_args()
    main(a.inst, a.dry)
