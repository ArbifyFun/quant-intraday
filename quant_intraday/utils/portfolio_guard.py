import os, json, datetime, fcntl
from dataclasses import dataclass

STATE_PATH = os.getenv("QI_RISK_STATE","/tmp/qi_risk_state.json")

@dataclass
class PortfolioLimits:
    daily_loss_limit_pct: float = 0.03
    max_concurrent_assets: int = 3

class PortfolioGuard:
    def __init__(self, limits: PortfolioLimits = PortfolioLimits()):
        self.limits=limits; self.path=STATE_PATH
        if not os.path.exists(self.path):
            self._write({"date":"", "equity_open":0.0, "equity_now":0.0, "instruments":{}, "entries_today":0})
    def _read(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path,"a+",encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX); f.seek(0)
            txt=f.read() or "{}"; import json; d=json.loads(txt); fcntl.flock(f, fcntl.LOCK_UN)
        return d
    def _write(self, obj):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(obj, f)
    def open_day(self, total_equity: float):
        s=self._read(); today=datetime.date.today().isoformat()
        if s.get("date")!=today:
            s={"date":today,"equity_open":float(total_equity),"equity_now":float(total_equity),"instruments":{},"entries_today":0}
            self._write(s)
    def can_enter(self, inst_id: str, est_worst_loss: float)->bool:
        s=self._read(); today=datetime.date.today().isoformat()
        if s.get("date")!=today: return True
        eq_open=float(s.get("equity_open",0.0)); eq_now=float(s.get("equity_now",eq_open))
        if eq_open>0 and (eq_open-eq_now+est_worst_loss) > self.limits.daily_loss_limit_pct*eq_open:
            return False
        active=[k for k,v in s.get("instruments",{}).items() if v.get("active",False)]
        if len(active)>=self.limits.max_concurrent_assets and inst_id not in active:
            return False
        return True
    def consume(self, inst_id: str, est_worst_loss: float):
        s=self._read(); s.setdefault("instruments",{})
        s["instruments"].setdefault(inst_id, {"active":True,"consumed":0.0})
        s["instruments"][inst_id]["active"]=True
        s["instruments"][inst_id]["consumed"] += float(est_worst_loss)
        s["entries_today"]=int(s.get("entries_today",0))+1
        self._write(s)
    def mark_pnl(self, total_equity_now: float):
        s=self._read(); s["equity_now"]=float(total_equity_now); self._write(s)
    def close_position(self, inst_id: str):
        s=self._read(); 
        if "instruments" in s and inst_id in s["instruments"]: s["instruments"][inst_id]["active"]=False
        self._write(s)
