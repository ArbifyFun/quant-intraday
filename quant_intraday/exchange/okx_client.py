import os, json, time, base64, hashlib, hmac, httpx

OKX_REST = "https://www.okx.com"

def okx_sign(ts: str, method: str, path: str, body: str, secret: str) -> str:
    msg = f"{ts}{method}{path}{body}".encode()
    mac = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

class OKXClient:
    def __init__(self, key, secret, passphrase, account="trade", timeout=10, simulated: bool | None = None):
        self.key, self.secret, self.passphrase = key, secret, passphrase
        self.account = account
        self.simulated = simulated if simulated is not None else (os.getenv("OKX_SIMULATED","0") == "1")
        self.rest = httpx.Client(base_url=OKX_REST, timeout=timeout)

    def _headers(self, method, path, body):
        ts = str(int(time.time()))
        sign = okx_sign(ts, method, path, body, self.secret)
        h = {
            "OK-ACCESS-KEY": self.key,
            "OK-ACCESS-SIGN": sign,
            "OK-ACCESS-TIMESTAMP": ts,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }
        # prefer official simulated header; fallback env switch OKX_ACCOUNT=paper is still read by some legacy stacks
        if self.simulated or os.getenv("OKX_ACCOUNT","").lower() in ("paper","demo","sim"):
            h["x-simulated-trading"] = "1"
        return h

    def get(self, path, params=None):
        r = self.rest.get(path, headers=self._headers("GET", path, ""), params=params or {})
        r.raise_for_status(); return r.json()

    def post(self, path, payload: dict):
        body = json.dumps(payload)
        r = self.rest.post(path, headers=self._headers("POST", path, body), content=body)
        r.raise_for_status(); return r.json()

    # ---- Convenience ----
    def get_balance(self, ccy="USDT"):
        j = self.get("/api/v5/account/balance")
        data = j.get("data",[{}])[0]
        for d in data.get("details", []):
            if d.get("ccy") == ccy: return float(d.get("eq", 0))
        return float(data.get("totalEq", 0))

    def get_instrument(self, inst_id):
        j = self.get("/api/v5/public/instruments", params={"instType":"SWAP"})
        for it in j.get("data", []):
            if it.get("instId") == inst_id: return it
        raise RuntimeError(f"Instrument not found: {inst_id}")

    def place_order(self, **kwargs):
        j = self.post("/api/v5/trade/order", kwargs)
        if j.get("code") != "0": raise RuntimeError(f"place_order error: {j}")
        return j["data"][0]

    def cancel_order(self, **kwargs):
        j = self.post("/api/v5/trade/cancel-order", kwargs)
        if j.get("code") != "0": raise RuntimeError(f"cancel_order error: {j}")
        return j["data"][0]

    # low-level (used by attribution/replay)
    def _get(self, path, params=None): return self.get(path, params)
    def _post(self, path, payload): return self.post(path, payload)
