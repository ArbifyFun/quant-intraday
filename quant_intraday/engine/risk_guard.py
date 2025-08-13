import json
import os
import time
from typing import Callable, Any, Dict

class RiskGuard:
    """Handle loading of risk control files and account level checks."""

    def __init__(self, control_path: str, risk_over_path: str, client: Any, pnl_func: Callable[[], float]):
        self._control_path = control_path
        self._risk_over_path = risk_over_path
        self.client = client
        self._pnl_func = pnl_func
        self.control: Dict[str, Any] = {}
        self._control_mtime: float | None = None
        self.risk_over: Dict[str, Any] = {}
        self._risk_over_mtime: float | None = None

    def load_control(self) -> bool:
        try:
            st = os.stat(self._control_path)
            if self._control_mtime != st.st_mtime:
                with open(self._control_path, "r", encoding="utf-8") as f:
                    self.control = json.load(f) or {}
                self._control_mtime = st.st_mtime
        except FileNotFoundError:
            self.control = {}
        except Exception:
            pass
        paused = False
        try:
            if isinstance(self.control, dict):
                if self.control.get("paused") is True:
                    paused = True
                pu = float(self.control.get("pause_until", 0) or 0)
                if pu and time.time() < pu:
                    paused = True
        except Exception:
            pass
        return paused

    def load_risk_overrides(self) -> None:
        try:
            st = os.stat(self._risk_over_path)
            if self._risk_over_mtime != st.st_mtime:
                with open(self._risk_over_path, "r", encoding="utf-8") as f:
                    self.risk_over = json.load(f) or {}
                self._risk_over_mtime = st.st_mtime
        except FileNotFoundError:
            self.risk_over = {}
        except Exception:
            pass

    def account_guard_denies(self, risk_amt: float) -> bool:
        self.load_control()
        c = self.control if isinstance(self.control, dict) else {}
        day_loss_usd = float(c.get("day_loss_limit_usd", 0) or 0)
        if day_loss_usd > 0:
            pnl = self._pnl_func()
            if pnl <= -abs(day_loss_usd):
                return True
        day_loss_pct = float(c.get("day_loss_limit_pct", 0) or 0)
        if day_loss_pct > 0:
            try:
                eq_now = self.client.get_balance("USDT")
                pnl = self._pnl_func()
                if eq_now > 0 and pnl < 0 and (-pnl / eq_now) >= day_loss_pct:
                    return True
            except Exception:
                pass
        return False

    def is_disabled(self, sig: Any) -> bool:
        try:
            from ..core.common import Signal  # lazy import
        except Exception:
            Signal = object  # type: ignore
        try:
            if not isinstance(sig, Signal):
                return False
        except Exception:
            return False
        try:
            self.load_control()
            ds = self.control.get("disable_strategies", [])
            if not ds:
                return False
            key = None
            if isinstance(sig.reason, str):
                key = sig.reason.split("|")[0].strip().lower()
            return key in {x.lower() for x in ds if isinstance(x, str)}
        except Exception:
            return False
