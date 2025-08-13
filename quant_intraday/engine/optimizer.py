import asyncio, time

class ExecOptimizer:
    """Book-aware limit execution with cancel/repost.
    - Aim to fill target size by repeatedly placing limits near top-of-book.
    - If not fully filled within slice_timeout_s, cancel & repost with more aggressive price.
    - If private WS is connected, checks order fill progress; otherwise, time-based.
    Params:
        step_ticks: price step each repost (ticks); positive -> more aggressive per cycle.
        max_reposts: safety cap on repost cycles.
        cross_when_last: if True, final cycle crosses spread (limit beyond opposite best).
    """
    def __init__(self, step_ticks:int=1, slice_timeout_s:int=3, max_reposts:int=5, cross_when_last:bool=True):
        self.step_ticks=step_ticks
        self.slice_timeout_s=slice_timeout_s
        self.max_reposts=max_reposts
        self.cross_when_last=cross_when_last

    def _filled_amount(self, bot, ord_id:str):
        try:
            ws = getattr(bot, "_private_ws", None)
            if ws is None: return 0.0
            od = ws.state.orders.get(ord_id, {})
            return float(od.get("accFillSz", 0.0))
        except Exception:
            return 0.0

    async def execute(self, bot, side:str, pos_side:str, total_sz:int, px_hint:float):
        """Returns list of order IDs placed (for trailing mgmt)."""
        remaining = int(total_sz); placed_ids=[]
        loop_ix = 0
        while remaining > 0 and loop_ix <= self.max_reposts:
            loop_ix += 1
            # price hint with aggressiveness
            px = bot._book_limit_px("buy" if pos_side=="long" else "sell", px_hint)
            # step aggressiveness each loop
            px = px + (self.step_ticks * bot._costs.tick_size) * (1 if side=="buy" else -1)
            # final crossing if enabled
            if loop_ix == self.max_reposts and self.cross_when_last:
                # cross one extra step
                px = px + (self.step_ticks * bot._costs.tick_size) * (1 if side=="buy" else -1)
            cur_sz = remaining
            clid=f"bot_opt_{int(time.time())}_{loop_ix}"
            if not bot.cfg.live:
                print(f"[DRY] OPT loop={loop_ix} {side}/{pos_side} sz={cur_sz} px={px:.6f}")
                # log event
                with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                    f.write(f"{int(time.time()*1000)},PLACE,{bot.cfg.inst_id},{side},{pos_side},{cur_sz},{px:.6f}\n")
                # emulate filled
                placed_ids.append(clid)
                break
            # live path
            try:
                resp = bot.client.place_order(instId=bot.cfg.inst_id, tdMode=bot.cfg.td_mode, side=side, posSide=pos_side,
                                              ordType="limit", sz=str(cur_sz), px=f"{px:.6f}", reduceOnly=False, clOrdId=clid)
                ord_id = resp.get("ordId", resp)
                placed_ids.append(ord_id)
                # monitor fill for timeout
                t0 = time.time()
                while time.time() - t0 < self.slice_timeout_s:
                    filled = self._filled_amount(bot, ord_id)
                    if filled >= cur_sz - 1e-9:
                        with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                            f.write(f"{int(time.time()*1000)},FILL_ALL,{bot.cfg.inst_id},{side},{pos_side},{cur_sz},{px:.6f}\n")
                        remaining -= cur_sz
                        break
                    await asyncio.sleep(0.5)
                else:
                    # timeout -> cancel & continue
                    try:
                        bot.client.cancel_order(instId=bot.cfg.inst_id, ordId=ord_id)
                        with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                            f.write(f"{int(time.time()*1000)},CANCEL,{bot.cfg.inst_id},{side},{pos_side},{cur_sz},{px:.6f}\n")
                    except Exception as e:
                        with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                            f.write(f"{int(time.time()*1000)},CANCEL_FAIL,{bot.cfg.inst_id},{side},{pos_side},{cur_sz},{px:.6f}\n")
                    # continue to next loop with more aggressive price
            except Exception as e:
                print("[OPT] place error:", e)
                with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                    f.write(f"{int(time.time()*1000)},PLACE_FAIL,{bot.cfg.inst_id},{side},{pos_side},{cur_sz},{px:.6f}\n")
                await asyncio.sleep(0.5)
        return placed_ids
