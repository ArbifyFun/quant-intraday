import asyncio

class AutoExecutor:
    """
    Runtime execution strategy selector:
    - If spread narrow & queue_pos poor -> Optimizer（更激进）
    - If spread normal & queue_pos中等 -> POV（小额多笔）
    - If spread宽/imbalance大 -> LOB（事件驱动maker，等待机会）
    Params:
      narrow_ticks, wide_ticks, qpos_aggr(<=x 视为队列位置差), qpos_ok(>=y 视为可耐心), prefer (maker|mixed|taker)
    """
    def __init__(self, narrow_ticks:int=1, wide_ticks:int=3, qpos_aggr:float=0.2, qpos_ok:float=0.5, prefer:str="mixed", cancel_budget_per_min:int=30):
        self.cancel_budget_per_min=cancel_budget_per_min
        self.narrow_ticks=narrow_ticks; self.wide_ticks=wide_ticks
        self.qpos_aggr=qpos_aggr; self.qpos_ok=qpos_ok; self.prefer=prefer

    async def execute(self, bot, side:str, pos_side:str, total_sz:int, px_hint:float):
        # read spread & queue position
        ticks=bot._costs.tick_size
        b=bot._books or {}
        bids=b.get("bids",[]); asks=b.get("asks",[])
        spread = (float(asks[0][0]) - float(bids[0][0])) if (bids and asks) else ticks
        spread_ticks = spread / ticks
        qpos = None
        # cancel budget: if超过上限，避免选择高撤单策略（optimizer/lob）
        if hasattr(bot, "_qtrk"):
            try:
                bids=b.get("bids",[]); asks=b.get("asks",[])
                qpos = bot._qtrk.on_book(bids, asks, ticks)
            except Exception:
                qpos = None
        # cancel budget: if超过上限，避免选择高撤单策略（optimizer/lob）
        # choose
        mode = None
        cancels_used = getattr(bot, '_cancel_used_1m', 0)
        budget_left = self.cancel_budget_per_min - cancels_used
        if spread_ticks <= self.narrow_ticks and (qpos is None or qpos <= self.qpos_aggr) and budget_left>0:
            mode="optimizer"
        elif spread_ticks >= self.wide_ticks and budget_left>0:
            mode="lob"
        else:
            mode="pov"
        # prefer maker bias
        if self.prefer=="maker" and mode=="optimizer":
            mode="pov"
        # dispatch
        if mode=="optimizer":
            from .optimizer import ExecOptimizer
            opt=ExecOptimizer(step_ticks=bot.cfg.opt_step_ticks, slice_timeout_s=bot.cfg.slice_timeout_s, max_reposts=bot.cfg.opt_max_reposts, cross_when_last=bot.cfg.opt_cross_last)
            return await opt.execute(bot, side, pos_side, total_sz, px_hint)
        elif mode=="pov":
            from .pov_executor import POVExecutor
            pov=POVExecutor(pov_rate=min(0.5, max(0.05, bot.cfg.prate)))
            return await pov.execute(bot, side, pos_side, total_sz, px_hint)
        else:
            from .lob_executor import LOBExecutor
            lob=LOBExecutor(bot.cfg.lob_widen_ticks, bot.cfg.lob_narrow_ticks, bot.cfg.lob_imb_th, bot.cfg.lob_queue_surge, bot.cfg.lob_min_dwell_s, bot.cfg.lob_max_cancels_per_min)
            return await lob.execute(bot, side, pos_side, total_sz, px_hint)
