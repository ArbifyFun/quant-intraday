import asyncio, time, os

class POVExecutor:
    """Lightweight POV: repeatedly place small child orders, tracking top-of-book.
    Params:
      pov_rate: 0<r<=1, fraction of remaining size per cycle
      min_child: min contracts per child
      adverse_ticks: reprice if mid moves adverse by this many ticks
      queue_max: if best-queue size > queue_max, consider crossing 1 tick on last cycles
      cycle_s: sleep between cycles
    Note: requires bot._books (books5) and bot._costs for tick_size.
    """
    def __init__(self, pov_rate: float=0.1, min_child:int=1, adverse_ticks:int=2, queue_max: float=5e3, cycle_s:int=2):
        self.pov_rate=pov_rate; self.min_child=min_child
        self.adverse_ticks=adverse_ticks; self.queue_max=queue_max; self.cycle_s=cycle_s

    def _best(self, bot):
        b=bot._books
        if not b: return None
        bids=b.get("bids",[]); asks=b.get("asks",[])
        best_bid = (float(bids[0][0]), float(bids[0][1])) if bids else (None, None)
        best_ask = (float(asks[0][0]), float(asks[0][1])) if asks else (None, None)
        mid = None
        if best_bid[0] and best_ask[0]:
            mid=(best_bid[0]+best_ask[0])/2.0
        return best_bid, best_ask, mid

    async def execute(self, bot, side:str, pos_side:str, total_sz:int, px_hint:float):
        remain = int(total_sz); ids=[]
        last_mid=None; ticks=bot._costs.tick_size
        while remain>0:
            best=self._best(bot)
            if not best:
                await asyncio.sleep(self.cycle_s); continue
            (bid_px,bid_q),(ask_px,ask_q),mid = best
            if last_mid is None: last_mid=mid
            # decide px: try to be maker; if queue too large near best, allow 1-tick cross on last chunk
            maker_px = bid_px if side=="buy" else ask_px
            cross_px = ask_px if side=="buy" else bid_px
            child = max(self.min_child, int(remain*self.pov_rate))
            # adverse move?
            adverse = ( (mid - last_mid)/ticks ) if side=="buy" else ( (last_mid - mid)/ticks )
            do_cross = False
            if abs(adverse) >= self.adverse_ticks:
                do_cross = True
            if (ask_q if side=="buy" else bid_q) > self.queue_max and remain <= child*2:
                do_cross = True
            # choose price
            if do_cross:
                place_px = cross_px if side=="buy" else cross_px
                # nudge one tick into opposite to ensure fill
                place_px = place_px + (1*ticks if side=="buy" else -1*ticks)
            else:
                place_px = maker_px
            place_px = bot._round_px(place_px)
            clid=f"pov_{int(time.time())}_{remain}"
            if not bot.cfg.live:
                print(f"[DRY] POV place sz={child} px={place_px:.6f} maker={not do_cross}")
                with open(os.path.join(bot._log_dir,"execlog.csv"),"a",encoding="utf-8") as f:
                    f.write(f"{int(time.time()*1000)},POV_PLACE,{bot.cfg.inst_id},{side},{pos_side},{child},{place_px:.6f}\n")
                ids.append(clid); remain-=child; last_mid=mid; await asyncio.sleep(self.cycle_s); continue

            # queue tracking (heuristic)
            try:
                from .queue_tracker import QueueTracker
                if not hasattr(bot, "_qtrk"): bot._qtrk = QueueTracker()
                bids=bot._books.get("bids", []) if bot._books else []
                asks=bot._books.get("asks", []) if bot._books else []
                best = bids[0] if side=="buy" and bids else (asks[0] if side!="buy" and asks else [place_px,0])
                bot._qtrk.on_new_order(side, float(child), float(best[0]), float(best[1]))
            except Exception:
                pass

            try:
                resp = bot.client.place_order(instId=bot.cfg.inst_id, tdMode=bot.cfg.td_mode, side=side, posSide=pos_side,
                                              ordType="limit", sz=str(child), px=f"{place_px:.6f}", reduceOnly=False, clOrdId=clid)
                ord_id = resp.get("ordId", resp); ids.append(ord_id); remain-=child
                with open(os.path.join(bot._log_dir,"execlog.csv"),"a",encoding="utf-8") as f:
                    f.write(f"{int(time.time()*1000)},{'POV_CROSS' if do_cross else 'POV_MAKE'},{bot.cfg.inst_id},{side},{pos_side},{child},{place_px:.6f}\n")
            except Exception as e:
                with open(os.path.join(bot._log_dir,"execlog.csv"),"a",encoding="utf-8") as f:
                    f.write(f"{int(time.time()*1000)},POV_PLACE_FAIL,{bot.cfg.inst_id},{side},{pos_side},{child},{place_px:.6f}\n")
            last_mid=mid
            await asyncio.sleep(self.cycle_s)
        return ids
