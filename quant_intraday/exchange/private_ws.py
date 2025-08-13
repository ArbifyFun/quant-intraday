import os, json, hmac, hashlib, base64, time, asyncio, websockets, logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable

from ..utils import logger as qi_logger

qi_logger.maybe_enable()
logger = logging.getLogger(__name__)

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
    def __init__(self, api_key:str, api_secret:str, passphrase:str, on_event: Optional[Callable[[str,Dict[str,Any],PrivateState],None]]=None):
        self.key=api_key; self.secret=api_secret; self.passphrase=passphrase; self.on_event=on_event
        self.state=PrivateState(); self._stop=False
    async def _login(self, ws):
        ts=str(int(time.time())); sign=_sign(ts,"GET","/users/self/verify","",self.secret)
        await ws.send(json.dumps({"op":"login","args":[{"apiKey":self.key,"passphrase":self.passphrase,"timestamp":ts,"sign":sign}]}))
    async def run(self):
        subs={"op":"subscribe","args":[{"channel":"account"},{"channel":"positions"},{"channel":"orders"}]}
        retries=0; delay=2
        while not self._stop:
            try:
                async with websockets.connect(OKX_WSS_PRIVATE, ping_interval=20) as ws:
                    retries=0; delay=2
                    await self._login(ws); await ws.send(json.dumps(subs))
                    async for msg in ws:
                        data=json.loads(msg)
                        if "event" in data: continue
                        ch=data.get("arg",{}).get("channel","")
                        for d in data.get("data", []):
                            if ch=="account": self.state.account=d
                            elif ch=="positions": self.state.positions[f"{d.get('instId','')}|{d.get('posSide','')}"]=d
                            elif ch=="orders": self.state.orders[d.get("ordId","")] = d
                            if self.on_event:
                                try: self.on_event(ch,d,self.state)
                                except Exception: pass
            except Exception as e:
                retries+=1; logger.warning("Private WS reconnect #%d in %.1fs: %s", retries, delay, e)
                await asyncio.sleep(delay); delay=min(delay*2,60)
    def stop(self): self._stop=True
