from datetime import datetime, timezone
import os, time, hmac, hashlib, base64, httpx, json

def _iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def okx_sign(secret: str, prehash: str) -> str:
    return base64.b64encode(hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()

class OKXClient:
    def __init__(self, key, secret, passphrase, account="trade", base_url="https://www.okx.com"):
        self.key, self.secret, self.passphrase, self.account = key, secret, passphrase, account
        self.base_url = base_url
        self.rest = httpx.Client(base_url=base_url, timeout=10.0)
        self._drift_ms = 0
        self._drift_at = 0

    def server_time_ms(self) -> int:
        r = self.rest.get("/api/v5/public/time", timeout=5.0)
        r.raise_for_status()
        return int(r.json()["data"][0]["ts"])

    def _iso_ts(self) -> str:
        try:
            return _iso_from_ms(self.server_time_ms())
        except Exception:
            now = int(time.time()*1000) + getattr(self, "_drift_ms", 0)
            return _iso_from_ms(now)

    def _headers(self, method: str, path: str, body: str):
        ts = self._iso_ts()
        prehash = f"{ts}{method.upper()}{path}{body or ''}"
        sign = okx_sign(self.secret, prehash)
        hdr = {
            "Content-Type": "application/json",
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
        }
        if os.getenv("OKX_SIMULATED","0") in ("1","true","True"):
            hdr["x-simulated-trading"] = "1"
        if os.getenv("QI_DEBUG_HTTP","0") not in ("0","false","False",""):
            safe = {k: ("***" if k.startswith("OK-ACCESS-") else v) for k,v in hdr.items()}
            print("[OKX][DBG] ts", ts)
            print("[OKX][DBG] pre-sign", {"method": method.upper(), "path": path, "body": body or ""})
            print("[OKX][DBG] headers", safe)
        return hdr

    def get_instrument(self, inst_id):
        r = self.rest.get("/api/v5/public/instruments?instType=SWAP")
        r.raise_for_status()
        for it in r.json()["data"]:
            if it.get("instId") == inst_id:
                return it
        raise RuntimeError(f"Instrument not found: {inst_id}")

    def get_balance(self, ccy="USDT"):
        path = "/api/v5/account/balance"
        r = self.rest.get(path, headers=self._headers("GET", path, ""))
        r.raise_for_status()
        data = r.json()["data"][0]
        for d in data.get("details", []):
            if d.get("ccy") == ccy:
                return float(d.get("eq", 0))
        return float(data.get("totalEq", 0))

    def place_order(self, **kwargs):
        path = "/api/v5/trade/order"
        payload = json.dumps(kwargs, separators=(",",":"))
        r = self.rest.post(path, headers=self._headers("POST", path, payload), content=payload)
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "0":
            raise RuntimeError(f"place_order error: {j}")
        return j["data"][0]
