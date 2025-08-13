#!/usr/bin/env python3
import os, asyncio, argparse
from quant_intraday.exchange.okx_client import OKXClient
from quant_intraday.engine.portfolio import PortfolioOrchestrator

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cfg", default="portfolio.yaml")
    p.add_argument("--risk", default=0.007, type=float)
    p.add_argument("--dd", default=0.08, type=float)
    a=p.parse_args()
    cli=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    orch=PortfolioOrchestrator(cli, cfg_path=a.cfg, risk_pct=a.risk, dd_limit=a.dd)
    asyncio.run(orch.run())

if __name__=="__main__":
    main()
