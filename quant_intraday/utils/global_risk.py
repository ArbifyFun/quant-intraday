import os, time, pandas as pd
from .notifier import notify

class GlobalRiskGuard:
    """Kill switch by daily drawdown on equity.csv (per-bot) or equity_*.csv (portfolio)."""
    def __init__(self, log_dir="live_output", dd_limit=0.08):
        self.log_dir=log_dir; self.dd_limit=dd_limit; self._tripped=False

    def tripped(self): return self._tripped

    def check(self):
        # Take latest equity*.csv if exists else return False
        import glob
        files=sorted(glob.glob(os.path.join(self.log_dir, "equity*.csv")))
        if not files: return False
        df=pd.read_csv(files[-1])
        if "equity" not in df.columns: return False
        eq=df["equity"]
        dd = (eq/eq.cummax()-1.0).min()
        if dd <= -abs(self.dd_limit):
            if not self._tripped:
                notify("global_dd_trip", {"dd": float(dd)})
            self._tripped=True
            return True
        return False
