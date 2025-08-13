#!/usr/bin/env python3
import os, json, time

LIVE=os.getenv("QI_LOG_DIR","live_output")
KPI=os.path.join(LIVE, "exec_kpis.json")
CONTROL=os.path.join(LIVE, "control.json")

DEFAULTS = {"enabled": True, "min_fill_rate": 0.35, "max_cancel_ratio": 3.0, "bounds_prate": [0.06, 0.20]}

def load_json(p, default):
    try: return json.load(open(p,"r"))
    except Exception: return default

def save_json(p, obj):
    tmp=p+".tmp"
    with open(tmp,"w",encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def decide(inst, kpi, conf):
    fr=float(kpi.get("fill_rate",0.0)); cr=float(kpi.get("cancel_ratio",0.0))
    low, high = conf.get("bounds_prate", DEFAULTS["bounds_prate"])
    pr = float(conf.get("prate_by_inst", {}).get(inst, (low+high)/2))
    mode = conf.get("exec_mode_by_inst", {}).get(inst, "autoexec")
    changed=False
    if fr < conf.get("min_fill_rate", DEFAULTS["min_fill_rate"]) and cr > conf.get("max_cancel_ratio", DEFAULTS["max_cancel_ratio"]):
        pr = max(low, pr * 0.8); mode = "pov"; changed=True
    elif fr > conf.get("min_fill_rate", DEFAULTS["min_fill_rate"]) + 0.2 and cr < conf.get("max_cancel_ratio", DEFAULTS["max_cancel_ratio"]) * 0.5:
        pr = min(high, pr * 1.2); mode = "optimizer"; changed=True
    return (pr, mode) if changed else None

def main():
    while True:
        ctl = load_json(CONTROL, {})
        auto = ctl.get("autotune", DEFAULTS)
        if not isinstance(auto, dict): auto = DEFAULTS
        if auto.get("enabled", True):
            kpis = load_json(KPI, {}).get("by_inst", {})
            pr_by = auto.get("prate_by_inst", {})
            mode_by = auto.get("exec_mode_by_inst", {})
            changed=False
            for inst, k in kpis.items():
                d = decide(inst, k, auto)
                if d:
                    pr, mo = d
                    pr_by[inst] = round(pr, 4)
                    mode_by[inst] = mo
                    changed=True
            if changed:
                auto["prate_by_inst"] = pr_by; auto["exec_mode_by_inst"] = mode_by
                ctl["autotune"] = auto
                save_json(CONTROL, ctl)
        time.sleep(20)

if __name__=="__main__":
    main()
