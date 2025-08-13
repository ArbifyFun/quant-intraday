#!/usr/bin/env python3
import os, time, json, glob
def main():
    live=os.getenv("QI_LOG_DIR","live_output")
    # recent execlog or trades within 15 minutes considered healthy
    paths=[os.path.join(live,"execlog.csv"), *glob.glob(os.path.join(live,"trades_*.csv"))[-1:]]
    now=time.time()
    for p in paths:
        if os.path.exists(p) and (now - os.path.getmtime(p) < 900):
            print("healthy:", p); return 0
    print("unhealthy"); return 1
if __name__=="__main__":
    raise SystemExit(main())
