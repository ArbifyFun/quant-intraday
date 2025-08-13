#!/usr/bin/env python3
import os, asyncio
from quant_intraday.engine.okx_push import OKXPrivateFeed

def main():
    live_dir=os.getenv("QI_LOG_DIR","live_output")
    feed=OKXPrivateFeed(live_dir)
    asyncio.run(feed.run())

if __name__=="__main__":
    main()
