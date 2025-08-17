import numpy as np
import pandas as pd

from .common import Signal
from ..utils.indicators import get_ta

ta = get_ta()

class BaseStrategy:
    """Shared helpers and default indicator calculations."""

    name = "base"

    @staticmethod
    def ema(series: pd.Series, period: int) -> np.ndarray:
        """Return the exponential moving average of ``series``."""

        return ta.EMA(series.to_numpy(), period)

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
        """Return the Average True Range for ``df``."""

        c = df["close"].to_numpy()
        h = df["high"].to_numpy()
        l = df["low"].to_numpy()
        return ta.ATR(h, l, c, period)

    def _ind(self, df: pd.DataFrame) -> pd.DataFrame:
        c = df["close"]
        h = df["high"]
        l = df["low"]
        v = df["volume"]
        ema20 = self.ema(c, 20)
        ema60 = self.ema(c, 60)
        atr14 = self.atr(df, 14)
        rsi14 = ta.RSI(c.to_numpy(), 14)
        bbu, bbm, bbl = ta.BBANDS(c.to_numpy(), 20, 2, 2)
        obv = ta.OBV(c.to_numpy(), v.to_numpy())
        out = df.copy()
        out["EMA20"], out["EMA60"] = ema20, ema60
        out["ATR"], out["RSI"] = atr14, rsi14
        out["BBU"], out["BBM"], out["BBL"] = bbu, bbm, bbl
        out["OBV"] = obv
        out["ATR_MA"] = out.ATR.rolling(14).mean()
        return out

class FundingBias(BaseStrategy):
    """Directional tilt based on funding rates."""

    name = "funding"

    def generate(self, df, micro=None):
        if micro is None:
            return None
        f = micro.get("funding", None)
        if f is None:
            return None
        # thresholds: high funding -> short bias; low funding -> long bias
        long_th, short_th = -0.02, 0.05  # annualized thresholds; tune via control.json in production
        if f >= short_th:
            # prefer SHORT with wide stop
            last = df.iloc[-1]["close"]
            atr = self.atr(df)[-1]
            if not np.isfinite(atr) or atr <= 0:
                return None
            return Signal(
                "SHORT",
                float(last),
                float(last + 1.2 * atr),
                float(last - 2.0 * atr),
                "funding short tilt",
            )
        if f <= long_th:
            last = df.iloc[-1]["close"]
            atr = self.atr(df)[-1]
            if not np.isfinite(atr) or atr <= 0:
                return None
            return Signal(
                "LONG",
                float(last),
                float(last - 1.2 * atr),
                float(last + 2.0 * atr),
                "funding long tilt",
            )
        return None

class BasisTilt(BaseStrategy):
    """Bias from futures basis (perp vs. quarterly)."""

    name = "basis"

    def generate(self, df, micro=None):
        if micro is None:
            return None
        bps = micro.get("basis_bps", None)
        if bps is None:
            return None
        last = df.iloc[-1]["close"]
        atr = self.atr(df)[-1]
        if not np.isfinite(atr) or atr <= 0:
            return None
        # same-exchange perp-vs-quarterly; large positive basis -> long tilt; large negative -> short tilt
        if bps >= 40:
            return Signal(
                "LONG",
                float(last),
                float(last - 1.0 * atr),
                float(last + 1.8 * atr),
                "basis long tilt",
            )
        if bps <= -40:
            return Signal(
                "SHORT",
                float(last),
                float(last + 1.0 * atr),
                float(last - 1.8 * atr),
                "basis short tilt",
            )
        return None


class StrategyTrend(BaseStrategy):
    """Breakout trend‑following strategy using EMA and Bollinger Bands."""

    name = "trend"

    def generate(self, df, micro=None):
        if len(df) < 80:
            return None
        ind = self._ind(df)
        prev = ind.iloc[-2]
        last = ind.iloc[-1]
        if not np.isfinite(last.ATR) or last.ATR <= 0:
            return None
        if (
            last.EMA20 > last.EMA60
            and last.close > last.BBU
            and last.RSI > 50
            and 45 <= prev.RSI <= 55
            and last.OBV > prev.OBV
            and last.ATR > last.ATR_MA * 1.1
        ):
            return Signal(
                "LONG",
                float(last.close),
                float(last.close - 1.2 * last.ATR),
                float(last.close + 2.0 * last.ATR),
                "trend long",
            )
        if (
            last.EMA20 < last.EMA60
            and last.close < last.BBL
            and last.RSI < 50
            and 45 <= prev.RSI <= 55
            and last.OBV < prev.OBV
            and last.ATR > last.ATR_MA * 1.1
        ):
            return Signal(
                "SHORT",
                float(last.close),
                float(last.close + 1.2 * last.ATR),
                float(last.close - 2.0 * last.ATR),
                "trend short",
            )
        return None

class StrategyPullbackTrend(StrategyTrend):
    """Enter in the direction of the trend after a brief pullback."""

    name = "pullback"

    def generate(self, df, micro=None):
        if len(df) < 80:
            return None
        ind = self._ind(df)
        last = ind.iloc[-1]
        prev = ind.iloc[-2]
        if (
            last.EMA20 > last.EMA60
            and last.RSI < 55
            and last.close > last.EMA20
            and prev.close < prev.BBM
            and last.close > last.BBM
        ):
            sl = float(min(ind.low.iloc[-5:]))
            tp = float(last.close + 2.0 * last.ATR)
            return Signal("LONG", float(last.close), sl, tp, "pullback long")
        if (
            last.EMA20 < last.EMA60
            and last.RSI > 45
            and last.close < last.EMA20
            and prev.close > prev.BBM
            and last.close < last.BBM
        ):
            sl = float(max(ind.high.iloc[-5:]))
            tp = float(last.close - 2.0 * last.ATR)
            return Signal("SHORT", float(last.close), sl, tp, "pullback short")
        return None

class StrategyRangeScalper(BaseStrategy):
    """Fade moves near the boundaries of a recent trading range."""

    name = "range"

    def generate(self, df, micro=None):
        if len(df) < 100:
            return None
        ind = self._ind(df)
        r = ind.iloc[-40:]
        rng = r.high.max() - r.low.min()
        if rng <= 0:
            return None
        price = ind.close.iloc[-1]
        if price < r.low.min() + 0.15 * rng and ind.RSI.iloc[-1] < 35:
            sl = float(r.low.min() - 0.5 * rng / 20)
            tp = float(ind.BBM.iloc[-1])
            return Signal("LONG", float(price), sl, tp, "range buy")
        if price > r.high.max() - 0.15 * rng and ind.RSI.iloc[-1] > 65:
            sl = float(r.high.max() + 0.5 * rng / 20)
            tp = float(ind.BBM.iloc[-1])
            return Signal("SHORT", float(price), sl, tp, "range sell")
        return None

class StrategyVWAPRevert(BaseStrategy):
    """Mean‑reversion to volume‑weighted average price."""

    name = "vwap"

    def generate(self, df, micro=None):
        if len(df) < 80:
            return None
        p = (df["high"] + df["low"] + df["close"]) / 3.0
        v = df["volume"].replace(0, 1.0)
        vwap = (p * v).cumsum() / v.cumsum()
        last = df.iloc[-1]
        vw = float(vwap.iloc[-1])
        c = float(last["close"])
        dev = (c - vw) / vw
        atr = float(self.atr(df)[-1])
        if atr != atr or atr <= 0:
            return None
        if dev < -0.003:
            return Signal("LONG", c, c - 1.2 * atr, vw, "vwap revert long")
        if dev > 0.003:
            return Signal("SHORT", c, c + 1.2 * atr, vw, "vwap revert short")
        return None

class StrategyIBBreakout(BaseStrategy):
    """Breakout of the initial balance range."""

    name = "ib"

    def generate(self, df, micro=None):
        if len(df) < 80:
            return None
        ib = df.iloc[-24:-12]  # first hour for 5m timeframe
        boxh, boxl = ib.high.max(), ib.low.min()
        last = df.iloc[-1]
        if last.close > boxh:
            atr = float(self.atr(df)[-1])
            return Signal(
                "LONG", float(last.close), float(last.close - 1.0 * atr), float(last.close + 2.0 * atr), "ib break long"
            )
        if last.close < boxl:
            atr = float(self.atr(df)[-1])
            return Signal(
                "SHORT", float(last.close), float(last.close + 1.0 * atr), float(last.close - 2.0 * atr), "ib break short"
            )
        return None

class StrategySqueezeBreakout(BaseStrategy):
    """Trade breakouts following a volatility squeeze."""

    name = "squeeze"

    def generate(self, df, micro=None):
        if len(df) < 120:
            return None
        c = df.close.to_numpy()
        bbu, bbm, bbl = ta.BBANDS(c, 20, 2, 2)
        bbw = (bbu - bbl) / bbm
        last = df.iloc[-1]
        if_squeeze = bbw[-1] < np.nanpercentile(bbw[-60:], 20)
        if not if_squeeze:
            return None
        atr = float(self.atr(df)[-1])
        if df.close.iloc[-1] > bbu[-1]:
            return Signal(
                "LONG", float(last.close), float(last.close - 1.1 * atr), float(last.close + 2.2 * atr), "squeeze long"
            )
        if df.close.iloc[-1] < bbl[-1]:
            return Signal(
                "SHORT", float(last.close), float(last.close + 1.1 * atr), float(last.close - 2.2 * atr), "squeeze short"
            )
        return None

class StrategyFailBreakoutReversal(BaseStrategy):
    """Fade failed Bollinger Band breakouts."""

    name = "fbr"

    def generate(self, df, micro=None):
        if len(df) < 100:
            return None
        ind = self._ind(df)
        prev, last = ind.iloc[-2], ind.iloc[-1]
        if prev.close > prev.BBU and last.close < last.BBU and last.RSI < prev.RSI:
            return Signal(
                "SHORT", float(last.close), float(last.close + 1.0 * last.ATR), float(last.BBM), "fail break short"
            )
        if prev.close < prev.BBL and last.close > last.BBL and last.RSI > prev.RSI:
            return Signal(
                "LONG", float(last.close), float(last.close - 1.0 * last.ATR), float(last.BBM), "fail break long"
            )
        return None

class StrategyOBIMomentum(BaseStrategy):
    """Order book imbalance momentum strategy."""

    name = "obi"

    def generate(self, df, micro=None):
        if len(df) < 80 or micro is None:
            return None
        imb = micro.get("imbalance", 0.0)
        ind = self._ind(df)
        last = ind.iloc[-1]
        if imb > 0.2 and last.RSI > 50 and last.EMA20 > last.EMA60:
            return Signal(
                "LONG",
                float(last.close),
                float(last.close - 1.0 * last.ATR),
                float(last.close + 1.8 * last.ATR),
                "obi long",
            )
        if imb < -0.2 and last.RSI < 50 and last.EMA20 < last.EMA60:
            return Signal(
                "SHORT",
                float(last.close),
                float(last.close + 1.0 * last.ATR),
                float(last.close - 1.8 * last.ATR),
                "obi short",
            )
        return None

class StrategyMomentumIgnition(BaseStrategy):
    """Detect sudden momentum bursts over the last few bars."""

    name = "mi"

    def generate(self, df, micro=None):
        if len(df) < 60:
            return None
        c = df.close
        r = (c.diff().rolling(4).sum()).iloc[-1]
        if r > 0.8:
            atr = float(self.atr(df)[-1])
            return Signal(
                "LONG", float(c.iloc[-1]), float(c.iloc[-1] - 1.0 * atr), float(c.iloc[-1] + 1.6 * atr), "mi long"
            )
        if r < -0.8:
            atr = float(self.atr(df)[-1])
            return Signal(
                "SHORT", float(c.iloc[-1]), float(c.iloc[-1] + 1.0 * atr), float(c.iloc[-1] - 1.6 * atr), "mi short"
            )
        return None

class AutoRouter:
    """Dispatch to multiple strategies based on configurable weights."""

    order = [
        "funding",
        "basis",
        "obi",
        "mi",
        "fbr",
        "ib",
        "squeeze",
        "pullback",
        "trend",
        "range",
        "vwap",
    ]

    def __init__(self, weights: dict | None = None):
        self.strats = {
            "funding": FundingBias(),
            "basis": BasisTilt(),
            "trend": StrategyTrend(),
            "pullback": StrategyPullbackTrend(),
            "range": StrategyRangeScalper(),
            "vwap": StrategyVWAPRevert(),
            "ib": StrategyIBBreakout(),
            "squeeze": StrategySqueezeBreakout(),
            "fbr": StrategyFailBreakoutReversal(),
            "obi": StrategyOBIMomentum(),
            "mi": StrategyMomentumIgnition(),
        }

    def route(self, df: pd.DataFrame, micro=None, weights: dict | None = None):
        order = list(self.order)
        w = weights or {}
        # sort by weight desc (default 1.0); weight<=0 disables
        order.sort(key=lambda k: w.get(k, 1.0), reverse=True)
        for k in order:
            if w.get(k, 1.0) <= 0:
                continue
            s = self.strats[k].generate(df, micro=micro)
            if s is not None:
                s.reason = f"{k} | " + s.reason
                return s
        return None
