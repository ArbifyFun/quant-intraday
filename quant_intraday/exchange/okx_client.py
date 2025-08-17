import os, json, time, base64, hashlib, hmac, httpx

OKX_REST = "https://www.okx.com"

def okx_sign(ts: str, method: str, path: str, body: str, secret: str) -> str:
    msg = f"{ts}{method}{path}{body}".encode()
    mac = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

class OKXClient:
    def __init__(
        self,
        key,
        secret,
        passphrase,
        account="trade",
        timeout=10,
        simulated: bool | None = None,
        max_retries: int = 3,
        backoff: float = 1.0,
    ):
        self.key, self.secret, self.passphrase = key, secret, passphrase
        self.account = account
        self.simulated = simulated if simulated is not None else (os.getenv("OKX_SIMULATED", "0") == "1")
        self.rest = httpx.Client(base_url=OKX_REST, timeout=timeout)
        self.max_retries = max_retries
        self.backoff = backoff

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

    def _sleep(self, attempt: int):
        time.sleep(self.backoff * (2 ** attempt))

    def get(self, path, params=None):
        for attempt in range(self.max_retries):
            r = self.rest.get(path, headers=self._headers("GET", path, ""), params=params or {})
            if r.status_code == 429 or r.status_code >= 500:
                self._sleep(attempt)
                continue
            try:
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == self.max_retries - 1:
                    raise
                self._sleep(attempt)
        raise RuntimeError("max retries exceeded")

    def post(self, path, payload: dict):
        body = json.dumps(payload)
        for attempt in range(self.max_retries):
            r = self.rest.post(path, headers=self._headers("POST", path, body), content=body)
            if r.status_code == 429 or r.status_code >= 500:
                self._sleep(attempt)
                continue
            try:
                r.raise_for_status()
                return r.json()
            except httpx.HTTPError:
                if attempt == self.max_retries - 1:
                    raise
                self._sleep(attempt)
        raise RuntimeError("max retries exceeded")

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
