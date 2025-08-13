import numpy as np
import pandas as pd
from quant_intraday.core.strategies import StrategyTrend, StrategyRangeScalper

def build_trend_df():
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    price = np.ones(n) * 100
    pattern = [100, 101] * 8  # 16 values; last is 101
    price[-16:] = pattern
    price[-2] = 100
    price[-1] = 105
    high = price + 0.5
    low = price - 0.5
    vol = np.ones(n) * 1000
    vol[-1] = 2000
    return pd.DataFrame({
        "open": price,
        "high": high,
        "low": low,
        "close": price,
        "volume": vol,
    }, index=idx)

def build_range_df():
    n = 120
    idx = pd.date_range("2024-01-01", periods=n, freq="1min")
    price = np.ones(n) * 100
    t = np.linspace(0, 2 * np.pi, 39, endpoint=False)
    price[-40:-1] = 100 + 5 * np.sin(t)
    price[-1] = 95
    high = price + 0.5
    low = price - 0.5
    vol = np.ones(n) * 1000
    return pd.DataFrame({
        "open": price,
        "high": high,
        "low": low,
        "close": price,
        "volume": vol,
    }, index=idx)

def test_strategy_trend_long_signal():
    df = build_trend_df()
    sig = StrategyTrend().generate(df)
    assert sig and sig.side == "LONG"

def test_strategy_trend_edge_cases():
    strat = StrategyTrend()
    assert strat.generate(build_trend_df().iloc[:70]) is None
    flat = pd.DataFrame({
        "open": np.ones(80) * 100,
        "high": np.ones(80) * 100,
        "low": np.ones(80) * 100,
        "close": np.ones(80) * 100,
        "volume": np.ones(80) * 1000,
    }, index=pd.date_range("2024-01-01", periods=80, freq="1min"))
    assert strat.generate(flat) is None

def test_strategy_range_scalper_long_signal():
    df = build_range_df()
    sig = StrategyRangeScalper().generate(df)
    assert sig and sig.side == "LONG"

def test_strategy_range_scalper_edge_cases():
    strat = StrategyRangeScalper()
    assert strat.generate(build_range_df().iloc[:80]) is None
    flat = pd.DataFrame({
        "open": np.ones(100) * 100,
        "high": np.ones(100) * 100,
        "low": np.ones(100) * 100,
        "close": np.ones(100) * 100,
        "volume": np.ones(100) * 1000,
    }, index=pd.date_range("2024-01-01", periods=100, freq="1min"))
    assert strat.generate(flat) is None
