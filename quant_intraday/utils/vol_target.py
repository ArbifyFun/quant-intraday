class VolTarget:
    """Scale risk toward a daily target volatility (e.g., 2%)."""
    def __init__(self, target_daily=0.02, floor=0.6, cap=1.6):
        self.target=target_daily; self.floor=floor; self.cap=cap
    def multiplier(self, atr_pct):
        # assume ATR% ~ daily vol proxy
        if atr_pct<=0: return 1.0
        m=self.target/atr_pct
        if m<self.floor: return self.floor
        if m>self.cap: return self.cap
        return m
