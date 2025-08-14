#!/usr/bin/env python3
import json
import os
import time
import pandas as pd
import logging

logger = logging.getLogger(__name__)

LIVE = os.getenv("QI_LOG_DIR", "live_output")
OUT = os.path.join(LIVE, "exec_kpis.json")


def compute():
    fp = os.path.join(LIVE, "execlog.csv")
    if not os.path.exists(fp):
        return {}
    try:
        df = pd.read_csv(fp)
    except Exception as e:
        logger.exception("failed to read execlog.csv: %s", e)
        return {}
    if df.empty:
        return {}
    df["ts"] = pd.to_numeric(df.get("ts"), errors="coerce").fillna(0).astype(int)
    df["evt"] = df.get("evt", "").astype(str)
    df["inst"] = df.get("inst", "").astype(str)
    res = {}
    now = int(time.time() * 1000)
    window = now - 60 * 60 * 1000
    d1 = df[df["ts"] >= window]
    for inst, g in d1.groupby("inst"):
        place = int((g["evt"] == "PLACE").sum())
        cancel = int((g["evt"] == "CANCEL").sum())
        fill = int((g["evt"].isin(["FILL", "PARTFILL"])).sum())
        fr = (fill / place) if place > 0 else 0.0
        cr = (cancel / max(place, 1))
        lt_ms = []
        gi = g.sort_values("ts")
        start = gi[gi["evt"] == "EXEC_START"]
        for _, s in start.iterrows():
            cl = str(s.get("clOrdId", ""))
            end = gi[(gi["clOrdId"].astype(str) == cl) & (gi["evt"].isin(["FILL", "CANCEL"]))]
            if not end.empty:
                lt_ms.append(int(end["ts"].iloc[-1]) - int(s["ts"]))
        p50 = float(pd.Series(lt_ms).median()) if lt_ms else 0.0
        p90 = float(pd.Series(lt_ms).quantile(0.9)) if lt_ms else 0.0
        res[inst] = {
            "fill_rate": fr,
            "cancel_ratio": cr,
            "lifetime_p50_ms": p50,
            "lifetime_p90_ms": p90,
            "place": place,
            "fill": fill,
            "cancel": cancel,
        }
    return res


def main():
    while True:
        try:
            r = compute()
            os.makedirs(LIVE, exist_ok=True)
            json.dump({"ts": int(time.time() * 1000), "by_inst": r}, open(OUT, "w"), ensure_ascii=False, indent=2)
        except Exception as e:
            logger.exception("exec_kpi_daemon loop error: %s", e)
        time.sleep(10)

if __name__=="__main__":
    main()
