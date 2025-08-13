from dataclasses import dataclass
from typing import Tuple

@dataclass
class RiskParams:
    risk_pct: float = 0.007
    daily_loss_limit_pct: float = 0.02
    scale_out: Tuple[Tuple[float,float], ...] = ((1.0,0.5),(1.5,0.25))
    breakeven_rr: float = 1.0
    trail_atr_mult: float = 1.0
    max_trades_per_day: int = 20

class RiskBudget:
    def __init__(self, day_equity: float, params: RiskParams):
        self.day_equity=float(day_equity); self.params=params
        self.consumed=0.0; self.trades=0
    @property
    def daily_limit(self)->float:
        return self.day_equity*self.params.daily_loss_limit_pct
    def can_open(self, worst_case_risk: float)->bool:
        if self.trades>=self.params.max_trades_per_day: return False
        return (self.consumed+max(0.0, worst_case_risk)) <= self.daily_limit
    def consume(self, worst_case_risk: float):
        self.consumed += max(0.0, worst_case_risk); self.trades += 1
