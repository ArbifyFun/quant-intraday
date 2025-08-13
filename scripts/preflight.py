#!/usr/bin/env python3
import os, sys, socket, time, json, httpx, traceback
from quant_intraday.exchange.okx_client import OKXClient

OKX_WSS_PUBLIC = "ws.okx.com"
REQUIRED_ENV = ["OKX_API_KEY","OKX_API_SECRET","OKX_API_PASSPHRASE"]

def check_env():
    missing=[k for k in REQUIRED_ENV if not os.getenv(k)]
    return {"ok": len(missing)==0, "missing": missing}

def check_dns(host):
    try:
        socket.getaddrinfo(host, None); return True
    except Exception: return False

def check_http(cli: OKXClient):
    try:
        me=httpx.get("https://www.okx.com").status_code==200
        ins=cli.get("/api/v5/public/instruments", params={"instType":"SWAP"})
        return {"ok": True, "samples": len(ins.get("data", []))>0}
    except Exception as e:
        return {"ok": False, "err": str(e)}

def check_balance(cli: OKXClient):
    try:
        eq=cli.get_balance("USDT")
        return {"ok": True, "equity": eq}
    except Exception as e:
        return {"ok": False, "err": str(e)}

def main():
    rep={"ts": int(time.time()*1000)}
    rep["env"]=check_env()
    rep["dns_public_ws"]=check_dns(OKX_WSS_PUBLIC)
    try:
        cli=OKXClient(os.getenv("OKX_API_KEY",""), os.getenv("OKX_API_SECRET",""), os.getenv("OKX_API_PASSPHRASE",""), os.getenv("OKX_ACCOUNT","trade"))
    except Exception as e:
        print(json.dumps({"ok":False,"err":str(e)})); sys.exit(1)
    rep["http"]=check_http(cli)
    rep["balance"]=check_balance(cli)
    ok = rep["env"]["ok"] and rep["dns_public_ws"] and rep["http"]["ok"]
    rep["ok"]=ok
    out=os.path.join(os.getenv("QI_LOG_DIR","live_output"), "preflight.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out,"w").write(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    sys.exit(0 if ok else 2)

if __name__=="__main__":
    main()
