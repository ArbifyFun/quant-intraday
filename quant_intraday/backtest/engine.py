import pandas as pd, numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple

from ..core.strategies import (
    StrategyTrend,
    StrategyVWAPRevert,
    StrategyIBBreakout,
    StrategyOBIMomentum,
    StrategyMomentumIgnition,
    StrategySqueezeBreakout,
    StrategyPullbackTrend,
    StrategyRangeScalper,
    StrategyFailBreakoutReversal,
    AutoRouter,
)
from ..utils.risk import RiskParams
from ..utils.indicators import get_ta

ta = get_ta()

@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: str
    entry: float
    exit: float
    size: float
    pnl: float
    pnl_pct: float
    bars: int
    reason: str


class ExecModel:
    @staticmethod
    def price(entry_px, side, tick, kyle_lambda=0.0, size_units=1.0, spread=0.0, mode="simple"):
        # simple: t+1 open +- slippage ticks
        if mode=="simple":
            return entry_px
        # kyle: impact = lambda * size
        imp = kyle_lambda * size_units
        if side=="LONG":
            return entry_px + imp + spread/2.0
        else:
            return entry_px - imp - spread/2.0

def estimate_spread(df_slice):
    mid = (df_slice["high"]+df_slice["low"])/2.0
    return float((df_slice["high"]-df_slice["low"]).median())*0.01  # crude 1% of median H-L as proxy


class Backtester:
    def __init__(self, strategy: str = "auto", risk: RiskParams = RiskParams(),
                 contract_value: float = 1.0, max_bars_in_trade: int = 48, sl_first: bool = True,
                 time_windows: Optional[List[Tuple[int,int]]] = None, tz: str = "UTC",
                 fee_bps: float = 5.0, tick_size: float = 0.1, slippage_ticks: int = 1,
                 exec_mode: str = "simple", kyle_lambda: float = 0.0):
        self.strategy_name=strategy; self.risk=risk; self.cv=contract_value
        self.max_bars=max_bars_in_trade; self.sl_first=sl_first; self.router=None; self.strategy=None
        self.time_windows=time_windows; self.tz=tz
        self.fee_bps=fee_bps; self.tick_size=tick_size; self.slippage_ticks=slippage_ticks
        self.exec_mode=exec_mode; self.kyle_lambda=kyle_lambda
        if strategy=="auto": self.router=AutoRouter()
        elif strategy=="trend": self.strategy=StrategyTrend()
        elif strategy=="vwap": self.strategy=StrategyVWAPRevert()
        elif strategy=="ib": self.strategy=StrategyIBBreakout()
        elif strategy=="obi": self.strategy=StrategyOBIMomentum()
        elif strategy=="mi": self.strategy=StrategyMomentumIgnition()
        elif strategy=="squeeze": self.strategy=StrategySqueezeBreakout()
        elif strategy=="pullback": self.strategy=StrategyPullbackTrend()
        elif strategy=="range": self.strategy=StrategyRangeScalper()
        elif strategy=="fbr": self.strategy=StrategyFailBreakoutReversal()
        else: self.router=AutoRouter()

    def _pos_size(self, equity:float, entry:float, sl:float)->float:
        risk_amt=equity*self.risk.risk_pct
        risk_per_unit=abs(entry-sl)*self.cv
        return 0.0 if risk_per_unit<=1e-12 else risk_amt/risk_per_unit

    def _allowed_time(self, ts: pd.Timestamp)->bool:
        if self.time_windows is None: return True
        lt = ts.tz_convert(self.tz).time(); m = lt.hour*60+lt.minute
        return any(s<=m<=e for s,e in self.time_windows)

    def _simulate_trade_path(self, df, i_entry, side, entry, sl0, tp0, atr_series):
        rr0=abs(entry-sl0); sl=sl0; be=False
        scales = sorted(self.risk.scale_out, key=lambda x:x[0]) if self.risk.scale_out else []
        scaled=[False]*len(scales)
        for j in range(i_entry, min(i_entry+self.max_bars, len(df)-1)):
            cur=df.iloc[j]; nxt=df.iloc[j+1]; h=float(nxt["high"]); l=float(nxt["low"])
            # scale-out hits
            for k,(rr,pct) in enumerate(scales):
                if scaled[k]: continue
                tgt = entry + (rr*rr0)*(1 if side=="LONG" else -1)
                if (side=="LONG" and h>=tgt) or (side=="SHORT" and l<=tgt): scaled[k]=True
            # breakeven
            if not be and self.risk.breakeven_rr is not None:
                be_tgt = entry + (self.risk.breakeven_rr*rr0)*(1 if side=="LONG" else -1)
                if (side=="LONG" and h>=be_tgt) or (side=="SHORT" and l<=be_tgt):
                    sl=entry; be=True
            # trailing
            if be and self.risk.trail_atr_mult and atr_series.notna().iloc[j]:
                atr=float(atr_series.iloc[j])
                if side=="LONG": sl=max(sl, float(nxt["close"]-self.risk.trail_atr_mult*atr))
                else: sl=min(sl, float(nxt["close"]+self.risk.trail_atr_mult*atr))
            # SL/TP checks
            hit_sl = (side=="LONG" and l<=sl) or (side=="SHORT" and h>=sl)
            hit_tp = (side=="LONG" and h>=tp0) or (side=="SHORT" and l<=tp0)
            if hit_sl and hit_tp: return (j+1, sl if self.sl_first else tp0, "SL&TP")
            if hit_sl: return (j+1, sl, "SL")
            if hit_tp: return (j+1, tp0, "TP")
        return (min(i_entry+self.max_bars, len(df)-1), float(df.iloc[min(i_entry+self.max_bars, len(df)-1)]["close"]), "TIME")

    def backtest(self, df: pd.DataFrame, equity0: float = 10_000.0) -> Dict:
        """
        Execute a vectorised backtest over a DataFrame of OHLCV bars.

        The backtester uses :func:`quant_intraday.utils.indicators.get_ta` to
        provide access to indicator functions.  This helper returns the real
        ``talib`` module when available and otherwise falls back to pure Python
        implementations, ensuring consistent behaviour across environments.
        """
        equity = equity0
        trades = []
        c,h,l = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
        atr = pd.Series(ta.ATR(h,l,c,14), index=df.index)

        def gen_signal(cur_df):
            if self.router is not None: return self.router.route(cur_df, micro=None)
            try: return self.strategy.generate(cur_df)
            except TypeError: return self.strategy.generate(cur_df, micro=None)

        for i in range(len(df)-1):
            ts=df.index[i]
            if not self._allowed_time(ts): continue
            cur_df=df.iloc[:i+1]; row=df.iloc[i]; nxt=df.iloc[i+1]
            sig = gen_signal(cur_df)
            if sig is None: continue
            entry=float(nxt["open"])
            # modelled execution impact
            spr = estimate_spread(df.iloc[max(0,i-200):i+1])
            entry = ExecModel.price(entry, sig.side, self.tick_size, self.kyle_lambda, size_units=1.0, spread=spr, mode=self.exec_mode)
            rr = abs(entry - sig.sl); 
            if rr<=1e-9: continue
            size=self._pos_size(equity, entry, sig.sl)
            if size<=0: continue
            j_exit, px_exit, why = self._simulate_trade_path(df, i+1, sig.side, entry, sig.sl, sig.tp, atr)
            px_adj = px_exit - (self.tick_size * self.slippage_ticks) if sig.side=="LONG" else px_exit + (self.tick_size * self.slippage_ticks)
            gross = (px_adj-entry)*size if sig.side=="LONG" else (entry-px_adj)*size
            notional_entry = entry*size*self.cv; notional_exit = px_adj*size*self.cv
            fees = (abs(notional_entry)+abs(notional_exit))*(self.fee_bps/10000.0)
            pnl = gross - fees; pnl_pct = pnl/equity if equity>0 else 0.0
            equity += pnl
            trades.append(Trade(entry_time=df.index[i+1], exit_time=df.index[j_exit], side=sig.side, entry=entry, exit=px_adj, size=size, pnl=pnl, pnl_pct=pnl_pct, bars=j_exit-(i+1), reason=sig.reason+"|"+why))

        eq = pd.Series([equity0], index=[df.index[0]])
        cur=equity0
        for t in trades: cur += t.pnl; eq.loc[t.exit_time]=cur
        eq = eq.sort_index().ffill()
        rets = eq.pct_change().fillna(0.0); ann = 365*24*60/5
        sharpe = (rets.mean()*ann)/(rets.std()+1e-12)
        cumret = eq.iloc[-1]/equity0 - 1.0; roll=eq.cummax(); mdd=((eq/roll)-1.0).min()
        summary=dict(equity_final=float(eq.iloc[-1]), return_total=float(cumret), sharpe=float(sharpe), max_drawdown=float(mdd),
                     trades=len(trades), winrate=float(np.mean([1.0 if t.pnl>0 else 0.0 for t in trades])) if trades else 0.0)
        return dict(summary=summary, trades=trades, equity=eq)
