#!/usr/bin/env python3
import argparse, asyncio, os, sys, json, signal, yaml

TEMPLATE = {"workers":[
    {"inst":"BTC-USDT-SWAP","tf":"5m","strategy":"auto","risk":0.006,"time_windows":"21:00-02:00","use_private":"true"},
    {"inst":"ETH-USDT-SWAP","tf":"5m","strategy":"auto","risk":0.006,"time_windows":"21:00-02:00","use_private":"true"},
    {"inst":"SOL-USDT-SWAP","tf":"5m","strategy":"auto","risk":0.005,"time_windows":"21:00-02:00","use_private":"true"},
]}

def load_config(path):
    if path.endswith(".yaml") or path.endswith(".yml"):
        with open(path,"r",encoding="utf-8") as f: return yaml.safe_load(f)
    with open(path,"r",encoding="utf-8") as f: return json.load(f)

async def run_worker(w):
    args=[sys.executable,"scripts/run_live.py","--inst",w["inst"],"--tf",w.get("tf","5m"),"--strategy",w.get("strategy","auto"),
          "--live", w.get("live","true"), "--risk", str(w.get("risk",0.006)),
          "--time-windows", w.get("time_windows","ALL"), "--use-private", w.get("use_private","true")]
    print("[SUP] start"," ".join(args))
    return await asyncio.create_subprocess_exec(*args)

async def main(config_path):
    if not os.path.exists(config_path):
        with open(config_path,"w",encoding="utf-8") as f: json.dump(TEMPLATE, f, ensure_ascii=False, indent=2)
        print("Wrote template manifest:", config_path); return
    cfg=load_config(config_path)
    procs=[]
    for w in cfg.get("workers", []):
        p=await run_worker(w); procs.append(p)
    async def shutdown():
        print("[SUP] shutting down...")
        for p in procs:
            try: p.terminate()
            except ProcessLookupError: pass
        await asyncio.sleep(1.0)
    loop=asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    while any(p.returncode is None for p in procs): await asyncio.sleep(3)

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--config", default="live_manifest.yaml"); a=p.parse_args(); asyncio.run(main(a.config))
