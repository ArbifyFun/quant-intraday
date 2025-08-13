from dotenv import load_dotenv, find_dotenv; load_dotenv(find_dotenv(usecwd=True))
#!/usr/bin/env python3
import os, json, sys, socket, time

OUT = os.path.join(os.getenv("QI_LOG_DIR","live_output"), "preflight.json")

def check_port(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

def main():
    res = {"ts": int(time.time()*1000)}
    # Python & TA-Lib
    try:
        import talib as ta  # noqa
        res["ta_lib"] = "ok"
    except ImportError as e:
        # Only catch missing module; other exceptions propagate
        res["ta_lib"] = f"error: {e}"
    # Web sockets DNS basic check
    res["okx_ws_public_dns"] = check_port("ws.okx.com", 8443)
    # ENV keys presence
    res["env"] = {
        "OKX_API_KEY": bool(os.getenv("OKX_API_KEY")),
        "OKX_API_SECRET": bool(os.getenv("OKX_API_SECRET")),
        "OKX_API_PASSPHRASE": bool(os.getenv("OKX_API_PASSPHRASE")),
        "OKX_SIMULATED": os.getenv("OKX_SIMULATED", "1"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, indent=2))

if __name__=="__main__":
    main()
