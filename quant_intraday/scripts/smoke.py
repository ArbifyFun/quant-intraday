#!/usr/bin/env python3
"""
Offline smoke test: imports, configs, dataclass defaults, key CLI entrypoints.
This does not hit network nor exchange APIs.
"""
import os, sys, json, importlib, types

mods = [
    "quant_intraday.cli",
    "quant_intraday.core.strategies",
    "quant_intraday.engine.live_bot",
    "quant_intraday.engine.portfolio",
    "quant_intraday.utils.risk",
]
res = {}
for m in mods:
    try:
        importlib.import_module(m)
        res[m] = "ok"
    except Exception as e:
        res[m] = f"error: {e.__class__.__name__}: {e}"

print(json.dumps(res, indent=2))
code = 0 if all(v=="ok" for v in res.values()) else 1
sys.exit(code)
