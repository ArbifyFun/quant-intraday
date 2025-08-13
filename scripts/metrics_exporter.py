#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge, Counter
import time, os, glob, pandas as pd

def main(port:int=8008, live_dir:str="live_output"):
    g_eq=Gauge("qi_equity","Equity from live_output/equity.csv")
    g_dd=Gauge("qi_drawdown","Drawdown from equity.csv")
    g_last_ts=Gauge("qi_equity_last_ts","Last equity ts")
    g_trades=Gauge("qi_recent_trades","Recent trade count across instruments")
    c_amend_ok=Counter("qi_amend_ok","Trailing amend success count")
    c_amend_fail=Counter("qi_amend_fail","Trailing amend fail count")
    c_risk_deny=Counter("qi_risk_deny","Risk deny events")
    c_exit_tp=Counter("qi_exit_tp","TP exits")
    c_exit_sl=Counter("qi_exit_sl","SL exits")
    c_exit_manual=Counter("qi_exit_manual","Manual/other exits")

    c_place = Counter("qi_exec_place", "Placed orders (optimizer/slicer)")
    c_cancel = Counter("qi_exec_cancel", "Cancelled orders")
    c_place_fail = Counter("qi_exec_place_fail", "Place failures")
    c_cancel_fail = Counter("qi_exec_cancel_fail", "Cancel failures")
    c_fill_all = Counter("qi_exec_fill_all", "Detected full fills")
    g_cancel_ratio = Gauge("qi_cancel_ratio", "Cancel ratio per scan (CANCEL/PLACE)")
    g_queue_depth = Gauge("qi_queue_depth", "Approx best queue (from execlog events)")
    g_queue_pos = Gauge("qi_queue_pos_est", "Estimated queue position ratio (heuristic) 0~1")

    start_http_server(port)
    while True:
        try:
            # queue pos (heuristic) if live_bot exposes _qtrk
            try:
                from quant_intraday.engine.queue_tracker import QueueTracker
            except Exception:
                pass
            # we can't access bot here; left as future hook via separate endpoint

            eq_p=os.path.join(live_dir,"equity.csv")
            if os.path.exists(eq_p):
                df=pd.read_csv(eq_p)
                if len(df)>0:
                    ts=float(df.iloc[-1,0]); eq=float(df.iloc[-1,1])
                    s=pd.Series(df.iloc[:,1]); dd=float((s/s.cummax()-1.0).iloc[-1])
                    g_eq.set(eq); g_dd.set(dd); g_last_ts.set(ts)
            cnt=0
            for f in glob.glob(os.path.join(live_dir, "trades_*.csv")):
                cnt += sum(1 for _ in open(f,"r",encoding="utf-8")) -1
            g_trades.set(cnt)
            trail_p=os.path.join(live_dir,"trail.log")
            if os.path.exists(trail_p):
                for line in open(trail_p,"r",encoding="utf-8"):
                    if "AMEND_OK" in line: c_amend_ok.inc()
                    elif "AMEND_FAIL" in line: c_amend_fail.inc()
            risk_p=os.path.join(live_dir,"risk.log")
            if os.path.exists(risk_p):
                for _ in open(risk_p,"r",encoding="utf-8"): c_risk_deny.inc()
        except Exception:
            pass

        # process execution log outside of the inner try so that
        # unexpected parsing errors don't break the main loop
        ex = os.path.join(live_dir, "execlog.csv")
        if os.path.exists(ex):
            p = c = 0
            with open(ex, "r", encoding="utf-8") as fh:
                for line in fh:
                    if ",PLACE" in line or ",POV_PLACE" in line or ",LOB_PLACE" in line:
                        p += 1
                        c_place.inc()
                    if ",CANCEL" in line:
                        c += 1
                        c_cancel.inc()
                    if ",PLACE_FAIL" in line or ",POV_PLACE_FAIL" in line or ",LOB_REPOST_FAIL" in line:
                        c_place_fail.inc()
                    if ",CANCEL_FAIL" in line:
                        c_cancel_fail.inc()
                    if ",FILL_ALL," in line:
                        c_fill_all.inc()
            g_cancel_ratio.set(c / (p + 1e-9))
            # queue depth proxy: count POV_MAKE vs POV_CROSS
            q = 0
            with open(ex, "r", encoding="utf-8") as fh:
                for line in fh:
                    if ",POV_MAKE," in line:
                        q += 1
                    elif ",POV_CROSS," in line:
                        q -= 1
            g_queue_depth.set(q)

        # process exits log
        exits = os.path.join(live_dir, "exits.log")
        if os.path.exists(exits):
            with open(exits, "r", encoding="utf-8") as fh:
                for line in fh:
                    if ",TP," in line:
                        c_exit_tp.inc()
                    elif ",SL," in line:
                        c_exit_sl.inc()
                    else:
                        c_exit_manual.inc()

        # throttle metric collection
        time.sleep(5)

if __name__=="__main__":
    import argparse; p=argparse.ArgumentParser(); p.add_argument("--port", default=8008, type=int); p.add_argument("--dir", default="live_output"); a=p.parse_args(); main(a.port, a.dir)
