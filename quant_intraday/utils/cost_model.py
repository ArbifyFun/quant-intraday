import os, yaml
from dataclasses import dataclass

DEFAULT_COSTS = {
  "default": {"taker_bps": 6.0, "maker_bps": 2.0, "tick_size": 0.1, "lot_size": 1.0, "entry_aggr_ticks": 1}
}

@dataclass
class CostSpec:
    taker_bps: float
    maker_bps: float
    tick_size: float
    lot_size: float
    entry_aggr_ticks: int = 1

def _load_yaml(path: str):
    if not os.path.exists(path): return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

def get_costs(client, inst_id: str, override_path: str = "costs.yaml") -> CostSpec:
    cfg = _load_yaml(override_path)
    if cfg and inst_id in cfg:
        d = cfg[inst_id]
        return CostSpec(taker_bps=float(d.get("taker_bps", 6.0)),
                        maker_bps=float(d.get("maker_bps", 2.0)),
                        tick_size=float(d.get("tick_size", 0.1)),
                        lot_size=float(d.get("lot_size", 1.0)),
                        entry_aggr_ticks=int(d.get("entry_aggr_ticks", 1)))
    # fallback to public instrument meta (tickSz/lotSz)
    try:
        meta = client.get_instrument(inst_id)
        tick = float(meta.get("tickSz", "0.1"))
        lot  = float(meta.get("lotSz", "1"))
        return CostSpec(taker_bps=6.0, maker_bps=2.0, tick_size=tick, lot_size=lot, entry_aggr_ticks=1)
    except Exception:
        d = DEFAULT_COSTS["default"]
        return CostSpec(**d)
