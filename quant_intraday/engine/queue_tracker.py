import time

class QueueTracker:
    """
    Heuristic best-queue position estimator.
    - Uses books5 best level size and our child order size (if known).
    - Assumes we are appended to the tail of best queue when we place a maker at best price.
    - Updates on each books5 event; estimates 'ahead' size and position ratio.
    """
    def __init__(self):
        self.best_px=None; self.best_q=0.0; self.my_sz=0.0; self.side=None; self.last_ts=0.0

    def on_new_order(self, side:str, size:float, best_px:float, best_q:float):
        self.side=side; self.my_sz=size; self.best_px=best_px; self.best_q=best_q; self.last_ts=time.time()

    def on_book(self, bids, asks, tick:float):
        if self.side is None: return 0.0
        # pick best level by side
        if self.side=="buy":
            if not bids: return 0.0
            px, q = float(bids[0][0]), float(bids[0][1])
        else:
            if not asks: return 0.0
            px, q = float(asks[0][0]), float(asks[0][1])
        # if best price moved, we assume our order got cancelled/reposted at new best => reset
        if self.best_px is None or abs(px - self.best_px) >= tick/2.0:
            self.best_px=px; self.best_q=q; self.last_ts=time.time()
            return 0.0
        # ahead size ~ current best queue excluding our own order (unknown), use q as proxy of "ahead"
        ahead=q
        # position ratio = my_sz / (ahead + my_sz); smaller => deeper
        pos = self.my_sz / max(1e-9, (ahead + self.my_sz))
        self.best_q=q; self.last_ts=time.time()
        return max(0.0, min(1.0, pos))
