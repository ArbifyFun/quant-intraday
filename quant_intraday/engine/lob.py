import asyncio, json, os, websockets, time
from dataclasses import dataclass
from typing import Dict, Optional

OKX_WSS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"

@dataclass
class Book:
    ts: int = 0
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_sz: float = 0.0
    ask_sz: float = 0.0
    spread: float = 0.0

class LOBFeed:
    def __init__(self, inst_id: str):
        self.inst_id = inst_id
        self.book = Book()
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        sub = {"op":"subscribe","args":[{"channel":"books5","instId": self.inst_id}]}
        while True:
            try:
                async with websockets.connect(OKX_WSS_PUBLIC, ping_interval=20) as ws:
                    await ws.send(json.dumps(sub))
                    async for msg in ws:
                        data = json.loads(msg)
                        if "event" in data: 
                            continue
                        for d in data.get("data", []):
                            ts=int(d.get("ts") or d.get("timestamp") or 0)
                            bids=d.get("bids", []); asks=d.get("asks", [])
                            if bids and asks:
                                bb=float(bids[0][0]); ba=float(asks[0][0])
                                bsz=float(bids[0][1]); asz=float(asks[0][1])
                                self.book = Book(ts=ts, best_bid=bb, best_ask=ba, bid_sz=bsz, ask_sz=asz, spread=ba-bb)
            except Exception as e:
                await asyncio.sleep(2)

    def ensure(self, loop):
        if self._task is None or self._task.done():
            self._task = loop.create_task(self.start())

    def qpos_estimate(self, side: str, px: float):
        """Very rough queue position estimator at placement time."""
        b = self.book
        if b.ts == 0 or px is None:
            return None
        if side.lower() == "buy":
            if px > b.best_ask:  # taker
                return 0.0
            if abs(px - b.best_bid) < 1e-8:
                return b.bid_sz
            if px < b.best_bid:
                return None  # away from book top
            return 0.0
        else: # sell
            if px < b.best_bid:
                return 0.0
            if abs(px - b.best_ask) < 1e-8:
                return b.ask_sz
            if px > b.best_ask:
                return None
            return 0.0
