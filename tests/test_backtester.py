import builtins
import pandas as pd
from types import SimpleNamespace
from quant_intraday.backtest.engine import Backtester, RiskParams


def _dummy_df():
    idx = pd.date_range("2024-01-01", periods=3, freq="5T", tz="UTC")
    data = {
        "open": [1.0, 1.0, 1.1],
        "high": [1.1, 1.1, 1.3],
        "low": [0.9, 0.95, 1.0],
        "close": [1.0, 1.0, 1.2],
    }
    return pd.DataFrame(data, index=idx)


class DummyStrategy:
    def __init__(self):
        self.called = False

    def generate(self, df, micro=None):
        if not self.called:
            self.called = True
            last = df["close"].iloc[-1]
            return SimpleNamespace(side="LONG", sl=last - 0.1, tp=last + 0.2, reason="dummy")
        return None


def test_backtester_basic_trade():
    df = _dummy_df()
    bt = Backtester(strategy="trend", risk=RiskParams())
    bt.strategy = DummyStrategy()
    res = bt.backtest(df)
    assert res["summary"]["trades"] == 1
    assert res["trades"][0].reason.endswith("TP")


def test_backtester_fallback(monkeypatch):
    df = _dummy_df()
    bt = Backtester(strategy="trend", risk=RiskParams())
    bt.strategy = DummyStrategy()

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "talib":
            raise ImportError
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    res = bt.backtest(df)
    assert res["summary"]["trades"] == 1
