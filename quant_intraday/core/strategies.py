import numpy as np
import pandas as pd

# Attempt to import the C extension for technical indicators.  If unavailable
# fall back to our pure‑Python implementations in utils.talib_fallback.  This
# wrapper makes it transparent for the rest of the strategy code to call
# indicator functions via ``ta.<func>``.
try:
    import talib as ta  # type: ignore
except ImportError:
    from ..utils.talib_fallback import (
        EMA as _EMA,
        ATR as _ATR,
        RSI as _RSI,
        BBANDS as _BBANDS,
        OBV as _OBV,
    )  # noqa: F401

    class _Fallback:
        @staticmethod
        def EMA(*args, **kwargs):
            return _EMA(*args, **kwargs)

        @staticmethod
        def ATR(*args, **kwargs):
            return _ATR(*args, **kwargs)

        @staticmethod
        def RSI(*args, **kwargs):
            return _RSI(*args, **kwargs)

        @staticmethod
        def BBANDS(*args, **kwargs):
            return _BBANDS(*args, **kwargs)

        @staticmethod
        def OBV(*args, **kwargs):
            return _OBV(*args, **kwargs)

    ta = _Fallback()
from .common import Signal

class BaseStrategy:
    name="base"
    def _ind(self, df):
        c=df["close"].to_numpy(); h=df["high"].to_numpy(); l=df["low"].to_numpy(); v=df["volume"].to_numpy()
        ema20,ema60 = ta.EMA(c,20), ta.EMA(c,60)
        atr14 = ta.ATR(h,l,c,14)
        rsi14 = ta.RSI(c,14)
        bbu,bbm,bbl = ta.BBANDS(c,20,2,2)
        obv = ta.OBV(c,v)
        out=df.copy()
        out["EMA20"],out["EMA60"],out["ATR"],out["RSI"],out["BBU"],out["BBM"],out["BBL"],out["OBV"]=ema20,ema60,atr14,rsi14,bbu,bbm,bbl,obv
        out["ATR_MA"]=out.ATR.rolling(14).mean()
        return out

class FundingBias(BaseStrategy):
    name = "funding"
    def generate(self, df, micro=None):
        if micro is None: return None
        f = micro.get("funding", None)
        if f is None: return None
        # thresholds: high funding -> short bias; low funding -> long bias
        long_th, short_th = -0.02, 0.05  # annualized thresholds; tune via control.json in production
        if f >= short_th:
            # prefer SHORT with wide stop
            last = df.iloc[-1]["close"]
            atr = ta.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), 14)[-1]
            if not np.isfinite(atr) or atr<=0: return None
            return Signal("SHORT", float(last), float(last+1.2*atr), float(last-2.0*atr), "funding short tilt")
        if f <= long_th:
            last = df.iloc[-1]["close"]
            atr = ta.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), 14)[-1]
            if not np.isfinite(atr) or atr<=0: return None
            return Signal("LONG", float(last), float(last-1.2*atr), float(last+2.0*atr), "funding long tilt")
        return None

class BasisTilt(BaseStrategy):
    name = "basis"
    def generate(self, df, micro=None):
        if micro is None: return None
        bps = micro.get("basis_bps", None)
        if bps is None: return None
        last = df.iloc[-1]["close"]
        atr = ta.ATR(df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), 14)[-1]
        if not np.isfinite(atr) or atr<=0: return None
        # same-exchange perp-vs-quarterly; large positive basis -> long tilt; large negative -> short tilt
        if bps >= 40:
            return Signal("LONG", float(last), float(last-1.0*atr), float(last+1.8*atr), "basis long tilt")
        if bps <= -40:
            return Signal("SHORT", float(last), float(last+1.0*atr), float(last-1.8*atr), "basis short tilt")
        return None


class StrategyTrend(BaseStrategy):
    name="trend"
    def generate(self, df, micro=None):
        if len(df)<80: return None
        # Fetch the last two rows explicitly.  Using ``iloc[-2:]`` returns a
        # two‑row DataFrame which would iterate over column names when
        # unpacked, leading to bugs.  Extract individual rows instead.
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
    name="pullback"
    def generate(self, df, micro=None):
        if len(df)<80: return None
        ind=self._ind(df); last=ind.iloc[-1]; prev=ind.iloc[-2]
        if last.EMA20>last.EMA60 and last.RSI<55 and last.close>last.EMA20 and prev.close<prev.BBM and last.close>last.BBM:
            sl=float(min(ind.low.iloc[-5:])); tp=float(last.close+2.0*last.ATR)
            return Signal("LONG", float(last.close), sl, tp, "pullback long")
        if last.EMA20<last.EMA60 and last.RSI>45 and last.close<last.EMA20 and prev.close>prev.BBM and last.close<last.BBM:
            sl=float(max(ind.high.iloc[-5:])); tp=float(last.close-2.0*last.ATR)
            return Signal("SHORT", float(last.close), sl, tp, "pullback short")
        return None

class StrategyRangeScalper(BaseStrategy):
    name="range"
    def generate(self, df, micro=None):
        if len(df)<100: return None
        ind=self._ind(df); r=ind.iloc[-40:]
        rng=r.high.max()-r.low.min()
        if rng<=0: return None
        if ind.close.iloc[-1]<r.low.min()+0.15*rng and ind.RSI.iloc[-1]<35:
            return Signal("LONG", float(ind.close.iloc[-1]), float(r.low.min()-0.5*rng/20), float(ind.BBM.iloc[-1]), "range buy")
        if ind.close.iloc[-1]>r.high.max()-0.15*rng and ind.RSI.iloc[-1]>65:
            return Signal("SHORT", float(ind.close.iloc[-1]), float(r.high.max()+0.5*rng/20), float(ind.BBM.iloc[-1]), "range sell")
        return None

class StrategyVWAPRevert(BaseStrategy):
    name="vwap"
    def generate(self, df, micro=None):
        if len(df)<80: return None
        p=(df["high"]+df["low"]+df["close"])/3.0
        v=df["volume"].replace(0,1.0); vwap=(p*v).cumsum()/v.cumsum()
        last=df.iloc[-1]; vw=float(vwap.iloc[-1]); c=float(last["close"])
        dev = (c-vw)/vw
        atr = float(ta.ATR(df["high"].to_numpy(),df["low"].to_numpy(),df["close"].to_numpy(),14)[-1])
        if atr!=atr or atr<=0: return None
        if dev<-0.003:
            return Signal("LONG", c, c-1.2*atr, vw, "vwap revert long")
        if dev>0.003:
            return Signal("SHORT", c, c+1.2*atr, vw, "vwap revert short")
        return None

class StrategyIBBreakout(BaseStrategy):
    name="ib"
    def generate(self, df, micro=None):
        if len(df)<80: return None
        ib = df.iloc[-24:-12]  # first hour (for 5m tf)
        boxh, boxl = ib.high.max(), ib.low.min()
        last=df.iloc[-1]
        if last.close>boxh:
            atr=float(ta.ATR(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(),14)[-1])
            return Signal("LONG", float(last.close), float(last.close-1.0*atr), float(last.close+2.0*atr), "ib break long")
        if last.close<boxl:
            atr=float(ta.ATR(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(),14)[-1])
            return Signal("SHORT", float(last.close), float(last.close+1.0*atr), float(last.close-2.0*atr), "ib break short")
        return None

class StrategySqueezeBreakout(BaseStrategy):
    name="squeeze"
    def generate(self, df, micro=None):
        if len(df)<120: return None
        c=df.close.to_numpy(); bbu,bbm,bbl = ta.BBANDS(c,20,2,2)
        bbw=(bbu-bbl)/bbm
        last=df.iloc[-1]; if_squeeze = bbw[-1] < np.nanpercentile(bbw[-60:], 20)
        if not if_squeeze: return None
        atr=float(ta.ATR(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(),14)[-1])
        if df.close.iloc[-1]>bbu[-1]:
            return Signal("LONG", float(last.close), float(last.close-1.1*atr), float(last.close+2.2*atr), "squeeze long")
        if df.close.iloc[-1]<bbl[-1]:
            return Signal("SHORT", float(last.close), float(last.close+1.1*atr), float(last.close-2.2*atr), "squeeze short")
        return None

class StrategyFailBreakoutReversal(BaseStrategy):
    name="fbr"
    def generate(self, df, micro=None):
        if len(df)<100: return None
        ind=self._ind(df); prev,last = ind.iloc[-2], ind.iloc[-1]
        # fake break above upper band and close back inside
        if prev.close>prev.BBU and last.close<last.BBU and last.RSI<prev.RSI:
            return Signal("SHORT", float(last.close), float(last.close+1.0*last.ATR), float(last.BBM), "fail break short")
        if prev.close<prev.BBL and last.close>last.BBL and last.RSI>prev.RSI:
            return Signal("LONG", float(last.close), float(last.close-1.0*last.ATR), float(last.BBM), "fail break long")
        return None

class StrategyOBIMomentum(BaseStrategy):
    name="obi"
    def generate(self, df, micro=None):
        if len(df)<80 or micro is None: return None
        # expect micro to be dict with 'imbalance' float from book
        imb = micro.get("imbalance", 0.0)
        ind=self._ind(df); last=ind.iloc[-1]
        if imb>0.2 and last.RSI>50 and last.EMA20>last.EMA60:
            return Signal("LONG", float(last.close), float(last.close-1.0*last.ATR), float(last.close+1.8*last.ATR), "obi long")
        if imb<-0.2 and last.RSI<50 and last.EMA20<last.EMA60:
            return Signal("SHORT", float(last.close), float(last.close+1.0*last.ATR), float(last.close-1.8*last.ATR), "obi short")
        return None

class StrategyMomentumIgnition(BaseStrategy):
    name="mi"
    def generate(self, df, micro=None):
        if len(df)<60: return None
        c=df.close
        r=(c.diff().rolling(4).sum()).iloc[-1]
        if r>0.8:
            atr=float(ta.ATR(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(),14)[-1])
            return Signal("LONG", float(c.iloc[-1]), float(c.iloc[-1]-1.0*atr), float(c.iloc[-1]+1.6*atr), "mi long")
        if r<-0.8:
            atr=float(ta.ATR(df.high.to_numpy(), df.low.to_numpy(), df.close.to_numpy(),14)[-1])
            return Signal("SHORT", float(c.iloc[-1]), float(c.iloc[-1]+1.0*atr), float(c.iloc[-1]-1.6*atr), "mi short")
        return None

class AutoRouter:
    order=["funding","basis","obi","mi","fbr","ib","squeeze","pullback","trend","range","vwap"]
    def __init__(self, weights: dict | None = None):
        self.strats={
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
        # sort by weight desc (default 1.0); weight<=0.0 effectively disables
        order.sort(key=lambda k: w.get(k, 1.0), reverse=True)
        for k in order:
            if w.get(k, 1.0) <= 0: continue
            s=self.strats[k].generate(df, micro=micro)
            if s is not None:
                s.reason = f"{k} | " + s.reason
                return s
        return None
