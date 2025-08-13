import os, time, pandas as pd

class PerformanceGuard:
    """Pause entries when rolling TP/SL quality deteriorates."""
    def __init__(self, log_dir="live_output", lookback=100, max_consec_loss=3, min_tp_ratio=0.35, cool_s=300):
        self.log_dir=log_dir; self.lookback=lookback; self.max_consec=max_consec_loss; self.min_tp=min_tp_ratio; self.cool_s=cool_s
        self._last_bad=0.0

    def _read_exits(self):
        fp=os.path.join(self.log_dir, "exits.log")
        if not os.path.exists(fp): return []
        rows=[]
        for line in open(fp,"r",encoding="utf-8"):
            try:
                ts,inst,pos,reason,px,sz=line.strip().split(",")
                rows.append((int(ts),reason))
            except Exception: continue
        return rows[-self.lookback:]

    def should_pause(self) -> bool:
        now=time.time()
        if now - self._last_bad < self.cool_s:
            return True
        rows=self._read_exits()
        if not rows: return False
        consec=0; tp_count=0; n=0
        for _,reason in rows:
            n+=1
            if reason=="TP": tp_count+=1; consec=0
            elif reason=="SL": consec+=1
        hit=tp_count/max(1,n)
        if consec>=self.max_consec or hit<self.min_tp:
            self._last_bad=now
            return True
        return False
