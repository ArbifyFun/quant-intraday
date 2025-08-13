import asyncio
import threading

import httpx

from quant_intraday.engine.live_bot import send_tg
from quant_intraday.exchange.okx_client import OKXClient


def test_send_tg_async(monkeypatch):
    called = {}

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        async def post(self, url, data=None, json=None, timeout=None):
            called["url"] = url
            return httpx.Response(200, json={"ok": True})

    async def run():
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "c")
        monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **k: DummyClient())
        await send_tg("hi")

    asyncio.run(run())
    assert called["url"].startswith("https://api.telegram.org")


def test_okx_client_place_order_async(monkeypatch):
    client = OKXClient("k", "s", "p")
    main_thread = threading.get_ident()

    def fake_place_order(**kwargs):
        # ensure executed in separate thread
        assert threading.get_ident() != main_thread
        return {"ordId": "1"}

    async def run():
        monkeypatch.setattr(client, "place_order", fake_place_order)
        res = await client.place_order_async(instId="BTC-USDT-SWAP")
        assert res["ordId"] == "1"

    asyncio.run(run())

