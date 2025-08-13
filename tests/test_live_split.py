import json
import asyncio
import pytest

from quant_intraday.engine.notifier import Notifier
from quant_intraday.engine.risk_guard import RiskGuard
from quant_intraday.engine.executor_manager import ExecutorManager
from quant_intraday.engine.live_bot import RunConfig

class DummyClient:
    def __init__(self):
        self.orders = []
    def get_balance(self, ccy: str) -> float:
        return 100.0
    def place_order(self, **kwargs):
        self.orders.append(kwargs)
        return {"ordId": f"oid{len(self.orders)}"}

def test_executor_manager_simple():
    cfg = RunConfig(inst_id="BTC-USDT-SWAP", exec_mode="simple")
    bot = type("B", (), {})()
    bot.scale_legs = [50, 50]
    bot.cfg = cfg
    bot.client = DummyClient()
    em = ExecutorManager(cfg)
    ids = asyncio.run(em.execute(bot, "buy", "long", 10, 100.0))
    assert ids == ["oid1", "oid2"]
    assert len(bot.client.orders) == 2

def test_risk_guard_account_deny(tmp_path):
    control = tmp_path / "control.json"
    control.write_text(json.dumps({"day_loss_limit_usd": 10}))
    rg = RiskGuard(str(control), str(tmp_path / "risk_overrides.json"), DummyClient(), lambda: -20.0)
    assert rg.account_guard_denies(1.0)

def test_notifier_send_tg(monkeypatch):
    from quant_intraday.engine import notifier as notifier_mod
    sent = {}
    def fake_post(url, data=None, timeout=None):
        sent['url'] = url
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "cid")
    monkeypatch.setattr(notifier_mod.httpx, "post", fake_post)
    n = Notifier()
    n.send_tg("hi")
    assert sent['url'].startswith("https://api.telegram.org/bottok/sendMessage")
