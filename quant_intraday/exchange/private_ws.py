import os, json, hmac, hashlib, base64, time, asyncio, websockets, logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable

OKX_WSS_PRIVATE = "wss://ws.okx.com:8443/ws/v5/private"

def _sign(ts: str, method: str, path: str, body: str, secret: str)->str:
    mac=hmac.new(secret.encode(), f"{ts}{method}{path}{body}".encode(), hashlib.sha256).digest()
    return base64.b64encode(mac).decode()

@dataclass
class PrivateState:
    account: Dict[str,Any] = field(default_factory=dict)
    positions: Dict[str,Any] = field(default_factory=dict)
    orders: Dict[str,Any] = field(default_factory=dict)

class OKXPrivateWS:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        passphrase: str,
        on_event: Optional[Callable[[str, Dict[str, Any], PrivateState], None]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.key = api_key
        self.secret = api_secret
        self.passphrase = passphrase
        self.on_event = on_event
        self.state = PrivateState()
        self._stop = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self.log = logger or logging.getLogger(__name__)

    async def _login(self, ws):
        ts=str(int(time.time())); sign=_sign(ts,"GET","/users/self/verify","",self.secret)
        await ws.send(json.dumps({"op":"login","args":[{"apiKey":self.key,"passphrase":self.passphrase,"timestamp":ts,"sign":sign}]}))
    async def run(self):
        subs = {
            "op": "subscribe",
            "args": [{"channel": "account"}, {"channel": "positions"}, {"channel": "orders"}],
        }
        attempt = 0
        delay = 1.0
        while not self._stop:
            try:
                async with websockets.connect(OKX_WSS_PRIVATE, ping_interval=20) as ws:
                    self._ws = ws
                    await self._login(ws)
                    await ws.send(json.dumps(subs))
                    attempt = 0
                    delay = 1.0
                    async for msg in ws:
                        data = json.loads(msg)
                        if "event" in data:
                            continue
                        ch = data.get("arg", {}).get("channel", "")
                        for d in data.get("data", []):
                            if ch == "account":
                                self.state.account = d
                            elif ch == "positions":
                                key = f"{d.get('instId','')}|{d.get('posSide','')}"
                                self.state.positions[key] = d
                            elif ch == "orders":
                                self.state.orders[d.get("ordId", "")] = d
                            if self.on_event:
                                try:
                                    self.on_event(ch, d, self.state)
                                except Exception:
                                    pass
            except Exception as e:
                attempt += 1
                self.log.warning(
                    "private_ws reconnect",
                    extra={"attempt": attempt, "error": str(e)},
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
            finally:
                self._ws = None

    async def close(self):
        """Signal the loop to stop and close the websocket."""

        self._stop = True
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    def stop(self):
        """Compatibility wrapper for old synchronous stop calls."""

        self._stop = True
