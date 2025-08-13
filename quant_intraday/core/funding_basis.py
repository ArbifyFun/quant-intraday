import time, math

class FundingBasisFeed:
    """Keep latest funding rate and same-exchange perp-vs-quarterly basis (bps)."""
    def __init__(self):
        self.last_funding = None  # annualized rate (e.g., 0.12 -> 12%)
        self.last_basis_bps = None  # basis in bps
        self.last_ts = 0

    def update_funding(self, rate_annual: float):
        self.last_funding = rate_annual; self.last_ts = time.time()

    def update_basis_bps(self, bps: float):
        self.last_basis_bps = bps; self.last_ts = time.time()

    def snapshot(self):
        return dict(funding=self.last_funding, basis_bps=self.last_basis_bps, ts=self.last_ts)


def funding_bias_signal(micro: dict, thresholds=(0.05, -0.05)) -> int:
    """Return +1/-1/0 bias by funding rate (annualized). thresholds=(long_th, short_th)."""
    if not micro: return 0
    f = micro.get("funding", None)
    if f is None: return 0
    if f >= thresholds[0]: return -1  # funding高 -> 做空倾向（收资金费）
    if f <= thresholds[1]: return +1  # funding低 -> 做多倾向
    return 0

def basis_tilt_signal(micro: dict, long_th=30, short_th=-30) -> int:
    """Return +1/-1/0 by same-exchange perp-vs-quarterly basis (bps)."""
    if not micro: return 0
    b = micro.get("basis_bps", None)
    if b is None: return 0
    if b <= short_th: return -1
    if b >= long_th:  return +1
    return 0
