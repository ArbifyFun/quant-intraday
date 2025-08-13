import time
from typing import List

from .slicer import SlicerExec
from .optimizer import ExecOptimizer
from .pov_executor import POVExecutor
from .lob_executor import LOBExecutor
from .autoexec import AutoExecutor

class ExecutorManager:
    """Select and dispatch to the configured execution strategy."""

    def __init__(self, cfg):
        self.cfg = cfg

    async def execute(self, bot, side: str, pos_side: str, sz_total: int, px: float) -> List[str]:
        order_ids: List[str] = []
        if self.cfg.exec_mode == "slicer":
            slicer = SlicerExec(self.cfg.prate, self.cfg.max_slices, self.cfg.slice_timeout_s)
            order_ids = await slicer.execute(bot, side, pos_side, int(sz_total), float(px))
        elif self.cfg.exec_mode == "optimizer":
            opt = ExecOptimizer(
                step_ticks=self.cfg.opt_step_ticks,
                slice_timeout_s=self.cfg.slice_timeout_s,
                max_reposts=self.cfg.opt_max_reposts,
                cross_when_last=self.cfg.opt_cross_last,
            )
            order_ids = await opt.execute(bot, side, pos_side, int(sz_total), float(px))
        elif self.cfg.exec_mode == "lob":
            lob = LOBExecutor(
                self.cfg.lob_widen_ticks,
                self.cfg.lob_narrow_ticks,
                self.cfg.lob_imb_th,
                self.cfg.lob_queue_surge,
                self.cfg.lob_min_dwell_s,
                self.cfg.lob_max_cancels_per_min,
            )
            order_ids = await lob.execute(bot, side, pos_side, int(sz_total), float(px))
        elif self.cfg.exec_mode == "pov":
            pov = POVExecutor(
                pov_rate=min(0.5, max(0.02, self.cfg.prate)),
                min_child=1,
                adverse_ticks=2,
                queue_max=5e3,
                cycle_s=max(1, int(self.cfg.slice_timeout_s)),
            )
            order_ids = await pov.execute(bot, side, pos_side, int(sz_total), float(px))
        elif self.cfg.exec_mode == "autoexec":
            auto = AutoExecutor()
            order_ids = await auto.execute(bot, side, pos_side, int(sz_total), float(px))
        else:
            legs = [p for p in bot.scale_legs if p > 0]
            for i, pct in enumerate(legs):
                leg_sz = max(1, int(float(sz_total) * (pct / 100.0)))
                clid = f"bot_{int(time.time())}_{i}"
                resp = bot.client.place_order(
                    instId=bot.cfg.inst_id,
                    tdMode=bot.cfg.td_mode,
                    side=side,
                    posSide=pos_side,
                    ordType="limit",
                    sz=str(leg_sz),
                    px=px,
                    reduceOnly=False,
                    clOrdId=clid,
                )
                order_ids.append(resp.get("ordId", resp))
        return order_ids
