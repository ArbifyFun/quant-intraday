import os, time, json, hmac, hashlib, base64, asyncio, websockets
from typing import Dict, Any
from ..utils.exelog import write_event

OKX_WSS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

def _sign(ts: str, method: str, path: str, body: str, secret: str) -> str:
    msg = f"{ts}{method}{path}{body}".encode()
    mac = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

class OKXPrivateFeed:
    def __init__(self, live_dir: str):
        self.key = os.getenv("OKX_API_KEY","")
        self.secret = os.getenv("OKX_API_SECRET","")
        self.passphrase = os.getenv("OKX_API_PASSPHRASE","")
        self.project = os.getenv("OKX_ACCOUNT","trade")
        self.live_dir = live_dir

    def _login_msg(self):
        ts = str(int(time.time()))
        sign = _sign(ts, "GET", "/users/self/verify", "", self.secret)
        return {"op":"login","args":[{"apiKey": self.key, "passphrase": self.passphrase, "timestamp": ts, "sign": sign}]}

    async def run(self):
        sub = {"op":"subscribe","args":[{"channel":"orders"}]}
        while True:
            try:
                async with websockets.connect(OKX_WSS_PRIVATE, ping_interval=20) as ws:
                    await ws.send(json.dumps(self._login_msg()))
                    # wait for login ok
                    ok=False
                    while True:
                        msg = json.loads(await ws.recv())
                        if "event" in msg and msg.get("event")=="login" and msg.get("code")=="0":
                            ok=True; break
                    if not ok: continue
                    await ws.send(json.dumps(sub))
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if "event" in data:
                            continue
                        for d in data.get("data", []):
                            self._on_order(d)
            except Exception as e:
                await asyncio.sleep(2)

    def _on_order(self, d: Dict[str, Any]):
        # OKX orders fields of interest
        evt = None
        state = d.get("state")  # live, canceled, partially_filled, filled
        fillSz = d.get("fillSz") or "0"
        fillPx = d.get("fillPx")
        side = d.get("side")
        inst = d.get("instId")
        px = d.get("px")
        sz = d.get("sz")
        clid = d.get("clOrdId")
        oid = d.get("ordId")
        reason = d.get("accFillSz")  # placeholder; OKX has 'cancelSource' sometimes

        if state == "canceled":
            evt = "CANCEL"
        elif state == "filled":
            evt = "FILL"
        elif state == "partially_filled":
            evt = "PARTFILL"
        elif state == "live":
            evt = "AMEND"  # could be ack or amend

        if evt is None:
            return

        try:
            write_event(os.path.join(self.live_dir, "execlog.csv"), {
                "ts": int(time.time()*1000),
                "evt": evt,
                "inst": inst,
                "side": side,
                "sz": sz,
                "px": float(px) if px else "",
                "fillSz": fillSz,
                "fillPx": float(fillPx) if fillPx else "",
                "state": state,
                "clOrdId": clid,
                "ordId": oid,
                "reason": reason or ""
            })
        except Exception:
            pass
