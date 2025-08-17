import os, json, hmac, time, base64, asyncio, hashlib, websockets
import numpy as np, pandas as pd
from dataclasses import dataclass, field
from typing import Optional, Deque, Dict
from collections import deque
from ..core.common import Signal
from ..core.strategies import AutoRouter, StrategyTrend, StrategyVWAPRevert, StrategyIBBreakout, StrategyOBIMomentum, StrategyMomentumIgnition, StrategySqueezeBreakout, StrategyPullbackTrend, StrategyRangeScalper, StrategyFailBreakoutReversal
from ..utils.time_windows import parse_time_windows, is_allowed_time
from ..utils.risk import RiskParams, RiskBudget
from ..utils.portfolio_guard import PortfolioGuard, PortfolioLimits
from ..utils.event_guard import EventGuard
from ..utils.cost_model import get_costs
from ..utils.calendar import TradeCalendar
from ..core.funding_basis import FundingBasisFeed
from ..utils.vol_target import VolTarget
from ..utils.perf_guard import PerformanceGuard
from ..exchange.private_ws import OKXPrivateWS
from ..exchange.okx_client import OKXClient
from .slicer import SlicerExec
from .optimizer import ExecOptimizer
from .pov_executor import POVExecutor
from .lob_executor import LOBExecutor
from .autoexec import AutoExecutor
from ..utils.notifier import send_tg, send_feishu

OKX_WSS_PUBLIC = "wss://ws.okx.com:8443/ws/v5/public"

def load_env(key:str)->str:
    v=os.getenv(key); 
    if v is None: raise RuntimeError(f"Missing env: {key}")
    return v

def okx_sign(ts: str, method: str, path: str, body: str, secret: str) -> str:
    msg = f"{ts}{method}{path}{body}".encode()
    mac = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


@dataclass
class Candle:
    ts:int; o:float; h:float; l:float; c:float; v:float

class CandleBuffer:
    def __init__(self, maxlen:int=4000):
        self.buf: Deque[Candle] = deque(maxlen=maxlen)
    def upsert(self, ts,o,h,l,c,v):
        if self.buf and self.buf[-1].ts==ts: self.buf[-1]=Candle(ts,o,h,l,c,v)
        elif self.buf and self.buf[-1].ts>ts: return
        else: self.buf.append(Candle(ts,o,h,l,c,v))
    def to_df(self):
        arr=[{"ts":x.ts,"open":x.o,"high":x.h,"low":x.l,"close":x.c,"volume":x.v} for x in self.buf]
        df=pd.DataFrame(arr); 
        if df.empty: return df
        df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True); df.set_index("dt", inplace=True); return df

@dataclass
class RunConfig:
    """
    Configuration container for a single instrument trading bot.  This class
    encapsulates all runtime tunables used by the live execution loop.  New
    fields should be given sensible defaults here to avoid attribute errors
    elsewhere in the codebase.

    Parameters
    ----------
    inst_id : str
        OKX instrument identifier (e.g. ``"BTC-USDT-SWAP"``).
    tf : str, default ``"5m"``
        Candlestick time frame passed to the market data subscription.
    live : bool, default ``False``
        When ``True`` orders will be sent to the exchange.  Otherwise
        execution is simulated and logs are written for analysis.
    risk_pct : float, default ``0.007``
        Daily risk budget as a percentage of account equity.
    td_mode : str, default ``"cross"``
        Trade mode for OKX (``"cross"`` or ``"isolated"``).
    strategy : str, default ``"auto"``
        High‑level strategy selector.  See ``core/strategies.py``.
    time_windows : str, default ``"ALL"``
        Allowed trading sessions as a comma‑separated list or ``"ALL"``.
    cooldown_s : int, default ``20``
        Minimum seconds between entries.
    risk_params : RiskParams
        Structure containing trailing/stop sizing parameters.
    scale_legs : str, default ``"50,30,20"``
        Percentage breakdown for splitting entries into multiple legs.
    use_private : bool, default ``False``
        When ``True`` subscribe to private order/trade events via WS.
    trailing_be_rr : float, default ``1.0``
        Risk‑reward multiple to trigger breakeven trailing stop.
    trailing_atr_mult : float, default ``1.0``
        ATR multiple used to tighten the stop once breakeven RR is hit.
    err_cb_threshold : int, default ``5``
        Number of REST errors within ``err_cb_window_s`` to trip circuit breaker.
    err_cb_window_s : int, default ``60``
        Sliding window in seconds for circuit breaker.
    err_cb_cool_s : int, default ``120``
        Cooldown in seconds after circuit breaker trips.

    Additional execution parameters
    ------------------------------
    min_atr_pct : float, default ``0.2``
        Minimum ATR percentile (0–1) below which trading is skipped.  Updated
        dynamically by ``autopilot_plus`` via ``thresholds.json``.
    min_vol_pct : float, default ``0.3``
        Minimum volume percentile (0–1) below which trading is skipped.
    adaptive_cool : bool, default ``True``
        Extend cooldown automatically during low‑quality regimes.
    exec_mode : str, default ``"autoexec"``
        Execution engine to use (``"simple"``, ``"slicer"``, ``"optimizer"``,
        ``"pov"``, ``"lob"`` or ``"autoexec"``).  ``autoexec`` delegates
        selection to the ``AutoExecutor``.
    prate : float, default ``0.12``
        Participation rate for POV/slicer executors (0–1).
    max_slices : int, default ``8``
        Maximum number of child orders for the slicer executor.
    slice_timeout_s : int, default ``3``
        Seconds to wait between successive child orders for optimizer/slicer.
    opt_step_ticks : int, default ``1``
        Step size in ticks for price improvement in the optimizer executor.
    opt_max_reposts : int, default ``5``
        Maximum number of cancel/repost attempts in the optimizer.
    opt_cross_last : bool, default ``True``
        Whether the optimizer should cross the spread on the final repost.
    lob_widen_ticks : int, default ``3``
        Spread widening threshold (in ticks) triggering a repost for the LOB executor.
    lob_narrow_ticks : int, default ``1``
        Spread narrowing threshold (in ticks) triggering a more aggressive repost.
    lob_imb_th : float, default ``0.2``
        Order‑book imbalance threshold beyond which LOB reposts.
    lob_queue_surge : float, default ``8000``
        Best‑queue size (contracts) above which the LOB executor will repost.
    lob_min_dwell_s : int, default ``2``
        Minimum seconds an order must rest on the book before it can be cancelled.
    lob_max_cxl_per_min : int, default ``20``
        Maximum number of cancellations per minute allowed for the LOB executor.
    """
    inst_id: str
    tf: str = "5m"
    live: bool = False
    risk_pct: float = 0.007
    td_mode: str = "cross"
    strategy: str = "auto"
    time_windows: str = "ALL"
    cooldown_s: int = 20
    risk_params: RiskParams = field(default_factory=RiskParams)
    scale_legs: str = "50,30,20"
    use_private: bool = False
    trailing_be_rr: float = 1.0
    trailing_atr_mult: float = 1.0
    err_cb_threshold: int = 5
    err_cb_window_s: int = 60
    err_cb_cool_s: int = 120
    # quality filtering and adaptive cooldown
    min_atr_pct: float = 0.20
    min_vol_pct: float = 0.30
    adaptive_cool: bool = True
    # execution engine selection and parameters
    exec_mode: str = "autoexec"
    prate: float = 0.12
    max_slices: int = 8
    slice_timeout_s: int = 3
    opt_step_ticks: int = 1
    opt_max_reposts: int = 5
    opt_cross_last: bool = True
    # limit order book executor parameters
    lob_widen_ticks: int = 3
    lob_narrow_ticks: int = 1
    lob_imb_th: float = 0.2
    lob_queue_surge: float = 8000.0
    lob_min_dwell_s: int = 2
    lob_max_cxl_per_min: int = 20
    # backward‑compatibility alias for max cancels per minute; both names refer to the same value
    lob_max_cancels_per_min: int = 20

def calc_contract_size(inst, quote_ccy_risk, entry_px):
    ct_sz=float(inst.get("ctVal")); lot=float(inst.get("lotSz","1"))
    sz = quote_ccy_risk/(entry_px*ct_sz)
    sz = max(lot, np.floor(sz/lot)*lot)
    return f"{sz:.0f}"

class Bot:
    def _today_pnl(self):
        """Approximate today's realized PnL using equity*.csv (latest file).
        Fallback 0 if file missing."""
        import glob, pandas as pd, time
        try:
            files=sorted(glob.glob(os.path.join(self._log_dir, "equity*.csv")))
            if not files: return 0.0
            df=pd.read_csv(files[-1])
            if df.empty: return 0.0
            # find first row of today (UTC)
            df['dt']=pd.to_datetime(df.get('dt', None) if 'dt' in df.columns else pd.to_datetime(df['ts'], unit='ms', utc=True))
            today = pd.Timestamp.utcnow().normalize()
            dft = df[df['dt']>=today]
            if dft.empty:
                # if no today's row, take delta from first to last overall
                return float(df['equity'].iloc[-1] - df['equity'].iloc[0]) if 'equity' in df.columns else 0.0
            start = float(dft['equity'].iloc[0]); last = float(dft['equity'].iloc[-1])
            return last - start
        except Exception:
            return 0.0

    def _account_guard_denies(self, risk_amt):
        """Check control.json risk constraints. Return True to block entry."""
        self._load_control()
        c = self._control if isinstance(self._control, dict) else {}
        # Daily loss limit USD
        day_loss_usd = float(c.get("day_loss_limit_usd", 0) or 0)
        if day_loss_usd > 0:
            pnl = self._today_pnl()
            if pnl <= -abs(day_loss_usd):
                return True
        # Daily loss limit %
        day_loss_pct = float(c.get("day_loss_limit_pct", 0) or 0)
        if day_loss_pct > 0:
            # estimate baseline equity as balance now / (1 + pnl%) ; conservative: block if risk exceeds margin under dd
            try:
                eq_now = self.client.get_balance("USDT")
                pnl = self._today_pnl()
                # if baseline unknown, treat as exceeded when eq drop exceeds pct
                if eq_now > 0 and pnl < 0 and (-pnl/eq_now) >= day_loss_pct:
                    return True
            except Exception:
                pass
        # Global pause flag already handled by _load_control in main loop
        # Max concurrent orders/positions can be approximated via cooling/last_fire but omitted for simplicity here
        return False

    def _is_disabled(self, sig):
        # control.json may contain {"disable_strategies": ["funding","basis", ...]}
        try:
            if not isinstance(sig, Signal):
                return False
        except Exception:
            return False
        try:
            self._load_control()
            ds = self._control.get("disable_strategies", [])
            if not ds: return False
            # infer strategy key from reason (before '|' if exists)
            key = None
            if isinstance(sig.reason, str):
                key = sig.reason.split('|')[0].strip().lower()
            return key in {x.lower() for x in ds if isinstance(x,str)}
        except Exception:
            return False

    def _load_control(self):
        import json, os, time
        try:
            st=os.stat(self._control_path)
            if not hasattr(self, "_control_mtime") or st.st_mtime != self._control_mtime:
                with open(self._control_path, "r", encoding="utf-8") as f:
                    self._control=json.load(f) or {}
                self._control_mtime=st.st_mtime
        except FileNotFoundError:
            self._control={}
        except Exception:
            pass
        # evaluate pause
        paused = False
        try:
            if isinstance(self._control, dict):
                if self._control.get("paused") is True:
                    paused = True
                pu = float(self._control.get("pause_until", 0) or 0)
                if pu and time.time() < pu:
                    paused = True
        except Exception:
            pass
        return paused

    def _load_risk_overrides(self):
        import json, os
        try:
            st=os.stat(self._risk_over_path)
            if not hasattr(self, "_risk_over_mtime") or st.st_mtime != self._risk_over_mtime:
                with open(self._risk_over_path, "r", encoding="utf-8") as f:
                    self._risk_over=json.load(f) or {}
                self._risk_over_mtime=st.st_mtime
        except FileNotFoundError:
            self._risk_over={}
        except Exception:
            pass

    def _refresh_funding_basis(self):
        try:
            # funding rate (next) for perp
            j=self.client.rest.get(f"/api/v5/public/funding-rate?instId={self.cfg.inst_id}").json()
            if j.get("code")=="0" and j.get("data"):
                fr=float(j["data"][0].get("nextFundingRate","0"))*3*365  # 8h rate -> annual
                self._fb.update_funding(fr)
        except Exception as e:
            pass
        try:
            # basis: perp mark vs quarterly futures last
            inst=self.cfg.inst_id; sym=inst.split("-")[0]
            # perp mark
            jp=self.client.rest.get(f"/api/v5/public/mark-price?instId={inst}").json()
            mark=float(jp["data"][0].get("markPx","nan"))
            # quarterly future (find instId containing this quarter code, fallback nearest)
            jj=self.client.rest.get("/api/v5/public/instruments?instType=FUTURES").json()
            futs=[x for x in jj.get("data",[]) if x.get("uly")==sym+"-USDT" or x.get("instId","").startswith(sym+"-USDT-")]
            fut=futs[0] if futs else None
            if fut:
                qid=fut.get("instId"); tq=self.client.rest.get(f"/api/v5/market/ticker?instId={qid}").json()
                last=float(tq["data"][0].get("last","nan"))
                bps=(last/mark-1.0)*10000.0
                self._fb.update_basis_bps(bps)
        except Exception as e:
            pass

    def _load_thresholds(self):
        import json, os
        try:
            st=os.stat(self._thresholds_path)
            if not hasattr(self, "_thresholds_mtime") or st.st_mtime != self._thresholds_mtime:
                with open(self._thresholds_path, "r", encoding="utf-8") as f:
                    self._thresholds=json.load(f) or {}
                self._thresholds_mtime=st.st_mtime
        except FileNotFoundError:
            self._thresholds={}
        except Exception:
            pass

    def _update_cancel_used(self):
        import time
        now=time.time()
        self._cancel_hist=[t for t in self._cancel_hist if now - t < 60]
        self._cancel_used_1m=len(self._cancel_hist)

    def _load_cooling(self):
        import json, os
        try:
            st=os.stat(self._cooling_path)
            if not hasattr(self, "_cooling_mtime") or st.st_mtime != self._cooling_mtime:
                with open(self._cooling_path, "r", encoding="utf-8") as f:
                    self._cooling=json.load(f) or {}
                self._cooling_mtime=st.st_mtime
        except FileNotFoundError:
            self._cooling={}
        except Exception:
            pass

    def _load_alloc(self):
        import json, os
        try:
            st=os.stat(self._alloc_path)
            if not hasattr(self, "_alloc_mtime") or st.st_mtime != self._alloc_mtime:
                with open(self._alloc_path, "r", encoding="utf-8") as f:
                    self._alloc=json.load(f) or {}
                self._alloc_mtime=st.st_mtime
        except FileNotFoundError:
            self._alloc={}
        except Exception:
            pass

    def _on_private_event(self, channel, data, state):
        # Tag exit triggers -> exits.log
        try:
            if channel=="orders":
                ord_type=str(data.get("ordType","")).lower()
                state_str=str(data.get("state",""))
                inst=str(data.get("instId",""))
                pos_side=str(data.get("posSide",""))
                if ord_type in ("take-profit","stop-loss") and state_str in ("filled","partially_filled"):
                    reason = "TP" if ord_type=="take-profit" else "SL"
                    with open(os.path.join(self._log_dir, "exits.log"), "a", encoding="utf-8") as f:
                        f.write(f"{int(time.time()*1000)},{inst},{pos_side},{reason},{data.get('avgPx','')},{data.get('accFillSz','')}\n")
        except Exception:
            pass

    def _round_px(self, px: float) -> float:
        ts = self._costs.tick_size
        return round(px / ts) * ts

    def _book_limit_px(self, side: str, fallback: float) -> float:
        try:
            book=self._books
            if not book: return self._round_px(fallback)
            asks=[float(a[0]) for a in book.get("asks", [])]
            bids=[float(b[0]) for b in book.get("bids", [])]
            if side=="buy":
                base = asks[0] if asks else fallback
                return self._round_px(base + self._costs.entry_aggr_ticks * self._costs.tick_size)
            else:
                base = bids[0] if bids else fallback
                return self._round_px(base - self._costs.entry_aggr_ticks * self._costs.tick_size)
        except Exception:
            return self._round_px(fallback)

    def _load_weights(self):
        import json, os, time
        try:
            st=os.stat(self._weights_path)
            if not hasattr(self, "_weights_mtime") or st.st_mtime != self._weights_mtime:
                with open(self._weights_path, "r", encoding="utf-8") as f:
                    self._weights=json.load(f) or {}
                self._weights_mtime=st.st_mtime
        except FileNotFoundError:
            self._weights={}
        except Exception:
            pass

    def __init__(self, cfg: RunConfig, client: OKXClient):
        self.cfg = cfg
        self.client = client
        self.buffer = CandleBuffer(4000)
        # Determine the base log directory.  Honour QI_LOG_DIR if it is
        # writeable, otherwise fall back to a local 'live_output'.  This
        # prevents OSError when the env path points at a read‑only filesystem.
        env_log = os.getenv("QI_LOG_DIR", "live_output")
        self._log_dir = env_log
        try:
            os.makedirs(self._log_dir, exist_ok=True)
        except OSError:
            # fallback to CWD
            self._log_dir = "live_output"
            os.makedirs(self._log_dir, exist_ok=True)

        self.router=AutoRouter() if cfg.strategy=="auto" else None
        self.strategy=None
        self._tw=parse_time_windows(cfg.time_windows)
        self.risk_params=cfg.risk_params
        self.scale_legs=[float(x) for x in (cfg.scale_legs.split(",") if cfg.scale_legs else ["100"])]
        self._budget=None; self._day_key=None
        self._pguard=PortfolioGuard(PortfolioLimits())
        self._events=EventGuard()
        self._calendar=TradeCalendar()
        self._books=None
        self._err_times=[]
        self._weights_path=os.path.join(self._log_dir, "weights.json")
        self._weights={}
        self._alloc_path=os.path.join(self._log_dir, "alloc.json")
        self._alloc={}
        self._cooling_path=os.path.join(self._log_dir, "cooling.json")
        self._cooling={}
        self._last_fire={}
        self._costs=get_costs(self.client, cfg.inst_id)
        self._thresholds_path=os.path.join(self._log_dir, "thresholds.json")
        self._thresholds={}
        self._risk_over_path=os.path.join(self._log_dir, "risk_overrides.json")
        self._risk_over={}
        self._control_path=os.path.join(self._log_dir, "control.json")
        self._control={}
        self._cancel_hist=[]
        self._cancel_used_1m=0
        self._fb=FundingBasisFeed()
        self._volt=VolTarget(target_daily=0.02)
        self._pguard=PerformanceGuard(self._log_dir)
        # _log_dir has been initialised above and directories created; do not reassign here
        self._trades_path=os.path.join(self._log_dir, f"trades_{cfg.inst_id.replace('/','-')}.csv")
        if not os.path.exists(self._trades_path):
            with open(self._trades_path,"w",encoding="utf-8") as f: f.write("ts,inst,side,price,sl,tp,size,reason\n")
        self._eq_path=os.path.join(self._log_dir, "equity.csv")
        if not os.path.exists(self._eq_path):
            with open(self._eq_path,"w",encoding="utf-8") as f: f.write("ts,equity\n")
        self._execlog = os.path.join(self._log_dir, "execlog.csv")
        if not os.path.exists(self._execlog):
            with open(self._execlog, "w", encoding="utf-8") as f: f.write("ts,evt,inst,side,pos,sz,px\n")

    async def run(self):
        await self._bootstrap_history()
        try:
            self._lob.ensure(asyncio.get_event_loop())
        except Exception:
            pass
        tasks=[self._ws_public_loop(), self._ws_books_trades_loop(), self._strategy_loop()]
        if self.cfg.use_private:
            self._private_ws = OKXPrivateWS(load_env("OKX_API_KEY"), load_env("OKX_API_SECRET"), load_env("OKX_API_PASSPHRASE"), on_event=self._on_private_event)
            tasks.append(self._private_ws.run())
        await asyncio.gather(*tasks)

    async def _bootstrap_history(self):
        path=f"/api/v5/market/candles?instId={self.cfg.inst_id}&bar={self.cfg.tf}&limit=200"
        r=self.client.rest.get(path); r.raise_for_status()
        for k in reversed(r.json()["data"]):
            ts=int(k[0]); o,h,l,c = map(float,k[1:5]); v=float(k[7] if len(k)>7 else (k[5] if len(k)>5 else 0.0))
            self.buffer.upsert(ts,o,h,l,c,v)

    async def _ws_public_loop(self):
        sub={"op":"subscribe","args":[{"channel":f"candle{self.cfg.tf}","instId":self.cfg.inst_id}]}
        while True:
            try:
                async with websockets.connect(self._wss_urls()[0], ping_interval=20, proxy=self._ws_proxy()) as ws:
                    await ws.send(json.dumps(sub))
                    async for msg in ws:
                        data=json.loads(msg)
                        if "event" in data: continue
                        for d in data.get("data", []):
                            ts=int(d[0]); o,h,l,c = map(float,d[1:5]); v=float(d[7] if len(d)>7 else 0.0)
                            self.buffer.upsert(ts,o,h,l,c,v)
            except Exception as e:
                print("WS public reconnect:", e); await asyncio.sleep(2)

    async def _ws_books_trades_loop(self):
        sub={"op":"subscribe","args":[{"channel":"books5","instId":self.cfg.inst_id}]}
        while True:
            try:
                async with websockets.connect(self._wss_urls()[1], ping_interval=20, proxy=self._ws_proxy()) as ws:
                    await ws.send(json.dumps(sub))
                    async for msg in ws:
                        data=json.loads(msg)
                        if "event" in data: continue
                        for d in data.get("data", []):
                            self._books = d
            except Exception as e:
                print("WS books reconnect:", e); await asyncio.sleep(2)

    def _estimate_vwap_slippage(self, side: str, notional: float) -> float:
        try:
            book=self._books
            if not book: return 0.0
            bids=[(float(p), float(sz)) for p,sz,_,_,_ in book.get("bids", [])]
            asks=[(float(p), float(sz)) for p,sz,_,_,_ in book.get("asks", [])]
            mid=(bids[0][0]+asks[0][0])/2.0
            rem=notional; v=0.0; q=0.0
            if side=="buy":
                for px,sz in asks:
                    take=min(rem, px*sz); v+=px*(take/px); q+=(take/px); rem-=take
                    if rem<=1e-9: break
            else:
                for px,sz in bids:
                    take=min(rem, px*sz); v+=px*(take/px); q+=(take/px); rem-=take
                    if rem<=1e-9: break
            if q<=0: return 0.0
            vwap=v/q; return abs(vwap-mid)
        except Exception:
            return 0.0

    async def _strategy_loop(self):
        cool_until=0
        while True:
            try:
                await asyncio.sleep(1)
                # equity snapshot + pguard
                try:
                    eq=self.client.get_balance("USDT")
                    with open(self._eq_path,"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},{eq}\n")
                    self._pguard.open_day(eq); self._pguard.mark_pnl(eq)
                except Exception: pass
                # daily budget init
                import datetime
                now_dt = datetime.datetime.utcnow().date()
                if (self._day_key is None) or (now_dt != self._day_key):
                    eq0=self.client.get_balance("USDT"); self._budget=RiskBudget(eq0, self.risk_params); self._day_key=now_dt
                # cooldown
                if time.time() < cool_until: continue
                df=self.buffer.to_df()
                if len(df)<120: continue

                # quality filters: ATR/Volume percentiles on last 500 bars
                try:
                    tail = df.tail(500)
                    # Compute ATR and volume percentiles.  Prefer TA‑Lib but fall back to
                    # our pure‑Python implementation if unavailable.  NumPy is already
                    # imported as ``np`` at the module top.
                    try:
                        import talib as ta  # type: ignore
                    except ImportError:
                        from ..utils.talib_fallback import ATR as _ATR  # noqa: F401
                        class _ta:
                            @staticmethod
                            def ATR(*args, **kwargs):
                                return _ATR(*args, **kwargs)
                        ta = _ta()  # type: ignore
                    c, h, l = tail["close"].to_numpy(), tail["high"].to_numpy(), tail["low"].to_numpy()
                    atr = ta.ATR(h, l, c, 14)
                    vol = tail["volume"].to_numpy()
                    atr_pct = (atr[-1] - np.nanmin(atr)) / (np.nanmax(atr) - np.nanmin(atr) + 1e-12)
                    vol_pct = (vol[-1] - np.nanmin(vol)) / (np.nanmax(vol) - np.nanmin(vol) + 1e-12)
                except Exception:
                    atr_pct = vol_pct = 1.0
                if atr_pct < self.cfg.min_atr_pct or vol_pct < self.cfg.min_vol_pct:
                    # low quality regime: extend cooldown
                    if self.cfg.adaptive_cool:
                        cool_until = time.time() + max(self.cfg.cooldown_s, 30)
                    continue

                # trading calendar
                is_open,why = self._calendar.is_open_now()
                if not is_open:
                    # closed or silent -> skip
                    await asyncio.sleep(5); continue
                # event blackout
                blocked,label=self._events.is_blocked(self.cfg.inst_id)
                if blocked:
                    print(f"[EVENT] Blackout {label}"); 
                    with open(os.path.join(self._log_dir,"risk.log"),"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},BLOCK,{label}\n")
                    try:
                        from ..utils.notifier import notify
                        notify('risk_block', {'label':label})
                    except Exception: pass
                    continue
                # refresh adaptive weights & alloc & thresholds
                self._load_weights(); self._load_alloc(); self._load_thresholds()
                # override min_atr_pct/min_vol_pct from thresholds.json if exists
                if 'min_atr_pct' in self._thresholds: self.cfg.min_atr_pct=float(self._thresholds['min_atr_pct'])
                if 'min_vol_pct' in self._thresholds: self.cfg.min_vol_pct=float(self._thresholds['min_vol_pct'])
                # web control (pause)
                # exec_mode override & prate override
                try:
                    self._load_control()
                    at = self._control.get('autotune', {}) if isinstance(self._control, dict) else {}
                    if isinstance(at, dict):
                        mo = at.get('exec_mode_by_inst', {}).get(self.cfg.inst_id)
                        if isinstance(mo, str): self.cfg.exec_mode = mo
                        pr = at.get('prate_by_inst', {}).get(self.cfg.inst_id)
                        if pr is not None:
                            self.cfg.prate = float(pr)
                except Exception:
                    pass
                
                if self._load_control():
                    await asyncio.sleep(2); continue
                # funding/basis refresh
                self._refresh_funding_basis()
                # build micro (simple imbalance if book available)
                micro=None
                if self._books:
                    bids=self._books.get("bids",[]); asks=self._books.get("asks",[])
                    bsum=sum(float(x[1]) for x in bids[:5]); asum=sum(float(x[1]) for x in asks[:5])
                    imb=(bsum-asum)/max(1e-9, (bsum+asum)); micro={"imbalance":imb}
                # generate
                if self.cfg.strategy=="auto":
                    sig=AutoRouter().route(df, micro=micro, weights=self._weights)
                else:
                    sig=AutoRouter().route(df, micro=micro, weights=self._weights)  # reuse
                # strategy-specific cooldown
                self._load_cooling()
                if sig is not None and isinstance(sig.reason, str) and '|' in sig.reason:
                    key=sig.reason.split('|')[0].strip()
                    cool=int(self._cooling.get(key, 0))
                    last=float(self._last_fire.get(key, 0))
                    if cool>0 and (time.time()-last) < cool:
                        sig=None

                if not sig: continue
                await self._execute_signal(sig)
                cool_until=time.time()+self.cfg.cooldown_s
            except Exception as e:
                print("Strategy loop error:", e); await asyncio.sleep(1)

    async def _execute_signal(self, sig: Signal):
        # REST error CB
        now=time.time(); self._err_times=[t for t in self._err_times if now - t < self.cfg.err_cb_window_s]
        if len(self._err_times)>=self.cfg.err_cb_threshold:
            print("[CB] REST errors threshold reached, cooling"); await asyncio.sleep(self.cfg.err_cb_cool_s); return
        equity=self.client.get_balance("USDT")
        # per-inst allocation multiplier (alloc.json: {"BTC-USDT-SWAP": 1.2, ...})
        mult = float(self._alloc.get(self.cfg.inst_id, 1.0)) if isinstance(self._alloc, dict) else 1.0
        # vol targeting multiplier based on last 100 bars ATR%
        df=self.buffer.to_df().tail(100)
        try:
            c = df['close'].to_numpy(); h = df['high'].to_numpy(); l = df['low'].to_numpy()
            # Use TA‑Lib if available; otherwise fall back to the pure‑Python ATR
            try:
                import talib as _ta  # type: ignore
            except ImportError:
                from ..utils.talib_fallback import ATR as _ATR  # noqa: F401
                class _ta:
                    @staticmethod
                    def ATR(*args, **kwargs):
                        return _ATR(*args, **kwargs)
            atr = _ta.ATR(h, l, c, 14)[-1]
            atrp = atr / max(1e-9, c[-1])
        except Exception:
            atrp = 0.01
        vt_mult=self._volt.multiplier(atrp)
        self._load_risk_overrides()
        over=float(self._risk_over.get(self.cfg.inst_id, 1.0)) if isinstance(self._risk_over, dict) else 1.0
        risk_amt=equity*self.cfg.risk_pct*mult*vt_mult*over
        # per-inst risk cap (USD) from control.json
        self._load_control()
        try:
            cap_map=self._control.get('per_inst_risk_cap_usd', {}) if isinstance(self._control, dict) else {}
            cap=float(cap_map.get(self.cfg.inst_id, 0) or 0)
            if cap>0:
                risk_amt=min(risk_amt, cap)
        except Exception:
            pass
        # account guard
        if self._account_guard_denies(risk_amt):
            print('[RISK] account guard deny entry'); return
        inst=self.client.get_instrument(self.cfg.inst_id)
        worst_per_unit=abs(sig.price-sig.sl)*float(inst.get("ctVal"))
        if self._budget and not self._budget.can_open(risk_amt):
            print("[Risk] Daily budget exhausted"); 
            with open(os.path.join(self._log_dir,"risk.log"),"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},BUDGET\n")
            return
        if not self._pguard.can_enter(self.cfg.inst_id, risk_amt):
            print("[Risk] Portfolio deny"); 
            with open(os.path.join(self._log_dir,"risk.log"),"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},PPORT\n")
            return
        est_slip=self._estimate_vwap_slippage("buy" if sig.side=="LONG" else "sell", risk_amt)
        print(f"[Signal] {sig.side} px={sig.price:.2f} sl={sig.sl:.2f} tp={sig.tp:.2f} risk={risk_amt:.2f} est_slip~{est_slip:.4f}")
        sz_total=calc_contract_size(inst, risk_amt, sig.price)
        side="buy" if sig.side=="LONG" else "sell"; pos_side="long" if sig.side=="LONG" else "short"
        px_lim = self._book_limit_px("buy" if sig.side=="LONG" else "sell", sig.price)
        sl_trigger, tp_trigger, px = f"{sig.sl:.4f}", f"{sig.tp:.4f}", f"{px_lim:.2f}"
        # dry-run
        if not self.cfg.live:
            print(f"[DRY] split {sz_total} legs {self.scale_legs}% px={px} tp={tp_trigger} sl={sl_trigger}")
            with open(self._trades_path,"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},{self.cfg.inst_id},{sig.side},{px},{sl_trigger},{tp_trigger},{sz_total},{sig.reason}\n")
            send_tg(f"ENTRY {self.cfg.inst_id} {sig.side} px={px} sl={sl_trigger} tp={tp_trigger} sz={sz_total}")
            if self._budget: self._budget.consume(risk_amt)
            self._pguard.consume(self.cfg.inst_id, risk_amt)
            return
        # live placement
        try:
            order_ids=[]
            if self.cfg.exec_mode == "slicer":
                slicer = SlicerExec(self.cfg.prate, self.cfg.max_slices, self.cfg.slice_timeout_s)
                order_ids = await slicer.execute(self, side, pos_side, int(sz_total), float(px))
            elif self.cfg.exec_mode == "optimizer":
                opt = ExecOptimizer(step_ticks=self.cfg.opt_step_ticks, slice_timeout_s=self.cfg.slice_timeout_s,
                                    max_reposts=self.cfg.opt_max_reposts, cross_when_last=self.cfg.opt_cross_last)
                order_ids = await opt.execute(self, side, pos_side, int(sz_total), float(px))
            elif self.cfg.exec_mode == "lob":
                # Use lob_max_cancels_per_min for backward compatibility with AutoExecutor.  A separate alias
                # ``lob_max_cxl_per_min`` exists on RunConfig for historical callers.
                lob = LOBExecutor(
                    self.cfg.lob_widen_ticks,
                    self.cfg.lob_narrow_ticks,
                    self.cfg.lob_imb_th,
                    self.cfg.lob_queue_surge,
                    self.cfg.lob_min_dwell_s,
                    self.cfg.lob_max_cancels_per_min,
                )
                order_ids = await lob.execute(self, side, pos_side, int(sz_total), float(px))
            elif self.cfg.exec_mode == "pov":
                pov = POVExecutor(pov_rate=min(0.5, max(0.02, self.cfg.prate)), min_child=1, adverse_ticks=2, queue_max=5e3, cycle_s=max(1,int(self.cfg.slice_timeout_s)))
                order_ids = await pov.execute(self, side, pos_side, int(sz_total), float(px))
            else:
                legs=[p for p in self.scale_legs if p>0]
                for i,pct in enumerate(legs):
                    leg_sz = max(1, int(float(sz_total)*(pct/100.0)))
                    clid=f"bot_{int(time.time())}_{i}"
                    resp=self.client.place_order(instId=self.cfg.inst_id, tdMode=self.cfg.td_mode, side=side, posSide=pos_side, ordType="limit", sz=str(leg_sz), px=px, reduceOnly=False, clOrdId=clid)
                    order_ids.append(resp.get("ordId", resp))
            # algo TP/SL
            self.client.order_algo(instId=self.cfg.inst_id, tdMode=self.cfg.td_mode, posSide=pos_side, ordType="take-profit", triggerPx=tp_trigger, orderPx=tp_trigger)
            self.client.order_algo(instId=self.cfg.inst_id, tdMode=self.cfg.td_mode, posSide=pos_side, ordType="stop-loss",  triggerPx=sl_trigger, orderPx=sl_trigger)
            with open(self._trades_path,"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},{self.cfg.inst_id},{sig.side},{px},{sl_trigger},{tp_trigger},{sz_total},{sig.reason}\n")
            send_tg(f"ENTRY {self.cfg.inst_id} {sig.side} px={px} sl={sl_trigger} tp={tp_trigger} sz={sz_total}")
            # trailing if enabled
            if self.cfg.trailing_be_rr or self.cfg.trailing_atr_mult:
                asyncio.create_task(self._trailing_amend_loop(order_ids, sig))
            if self._budget: self._budget.consume(risk_amt)
            self._pguard.consume(self.cfg.inst_id, risk_amt)
        except Exception as e:
            print("[LIVE] order error:", e); self._err_times.append(time.time())

    async def _trailing_amend_loop(self, ord_ids, sig):
        # We need ATR for trailing stop calculation; try TA‑Lib first,
        # otherwise use our pure‑Python fallback.  If neither is available
        # return early without trailing amendments.
        try:
            try:
                import talib as ta  # type: ignore
            except ImportError:
                from ..utils.talib_fallback import ATR as _ATR  # noqa: F401
                class _ta:
                    @staticmethod
                    def ATR(*args, **kwargs):
                        return _ATR(*args, **kwargs)
                ta = _ta()  # type: ignore
        except Exception:
            return
        step=10; last_sl=sig.sl
        while True:
            await asyncio.sleep(step)
            df=self.buffer.to_df()
            if len(df)<60: continue
            last=df.iloc[-1]
            c,h,l=df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
            atr=ta.ATR(h,l,c,14)[-1]
            if not (atr==atr): continue
            px=float(last["close"]); rr0=abs(sig.price-sig.sl)
            progressed=(px-sig.price) if sig.side=="LONG" else (sig.price-px)
            if progressed < self.cfg.trailing_be_rr*rr0: continue
            if sig.side=="LONG":
                new_sl=max(last_sl, px - self.cfg.trailing_atr_mult*float(atr))
                if new_sl<=last_sl: continue
            else:
                new_sl=min(last_sl, px + self.cfg.trailing_atr_mult*float(atr))
                if new_sl>=last_sl: continue
            last_sl=new_sl; sl_trigger=f"{new_sl:.4f}"
            try:
                # try amend orders; fallback cancel+new algo
                for oid in ord_ids:
                    try:
                        self.client.amend_order(instId=self.cfg.inst_id, ordId=oid, slTriggerPx=sl_trigger, slOrdPx=sl_trigger)
                    except Exception:
                        self.client.cancel_algo(instId=self.cfg.inst_id, ordType="stop-loss")
                        self.client.order_algo(instId=self.cfg.inst_id, tdMode=self.cfg.td_mode, posSide=("long" if sig.side=="LONG" else "short"), ordType="stop-loss", triggerPx=sl_trigger, orderPx=sl_trigger)
                with open(os.path.join(self._log_dir,"trail.log"),"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},AMEND_OK,{sl_trigger}\n")
                send_tg(f"TRAIL {self.cfg.inst_id} SL->{sl_trigger}")
            except Exception as e:
                with open(os.path.join(self._log_dir,"trail.log"),"a",encoding="utf-8") as f: f.write(f"{int(time.time()*1000)},AMEND_FAIL,{sl_trigger}\n")
                print("[TRAIL] amend error:", e)

# ---- Safety fallback: ensure Bot has _wss_urls/_ws_proxy even if older builds miss them ----
def _qi_bot_wss_urls(self):
    import os
    sim = os.getenv("OKX_SIMULATED","0") in ("1","true","True")
    broker = os.getenv("OKX_DEMO_BROKER_ID","9999")
    if sim:
        base = f"wss://wspap.okx.com:8443/ws/v5/business?brokerId={broker}"
        return base, base
    else:
        pub = os.getenv("OKX_WSS_PUBLIC","wss://ws.okx.com:8443/ws/v5/public")
        prv = os.getenv("OKX_WSS_PRIVATE","wss://ws.okx.com:8443/ws/v5/private")
        return pub, prv

def _qi_bot_ws_proxy(self):
    import os
    mode = os.getenv("QI_PROXY_MODE","off").lower()
    if mode == "off":
        return None
    return os.getenv("QI_WS_PROXY") or os.getenv("QI_HTTPS_PROXY") or os.getenv("QI_HTTP_PROXY")

try:
    if not hasattr(Bot, "_wss_urls"):
        Bot._wss_urls = _qi_bot_wss_urls
    if not hasattr(Bot, "_ws_proxy"):
        Bot._ws_proxy = _qi_bot_ws_proxy
except NameError:
    # Bot not defined yet in some import orders; ignore.
    pass
