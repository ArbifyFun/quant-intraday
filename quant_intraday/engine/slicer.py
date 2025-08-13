import asyncio, time

class SlicerExec:
    """Very simple participation-style slicer.
    - Split total size into <= max_slices slices.
    - Each slice places a limit at book-aware price hint.
    - Wait slice_timeout_s; then move on to next slice (best-effort, no fill check).
    """
    def __init__(self, prate: float = 0.1, max_slices: int = 8, slice_timeout_s: int = 3):
        self.prate=prate; self.max_slices=max_slices; self.slice_timeout_s=slice_timeout_s

    async def execute(self, bot, side: str, pos_side: str, total_sz: int, px_hint: float):
        """bot: reference to live Bot (has client, _book_limit_px, cfg)"""
        if total_sz <= 0:
            return []
        sz_left = int(total_sz)
        order_ids = []
        slices = max(1, min(self.max_slices, sz_left))
        per = max(1, sz_left // slices)
        # naive loop
        for i in range(slices):
            if sz_left <= 0: break
            cur_sz = per if i < slices-1 else sz_left
            # adjust px using current book
            px = bot._book_limit_px("buy" if pos_side=="long" else "sell", px_hint)
            clid=f"bot_slice_{int(time.time())}_{i}"
            if not bot.cfg.live:
                print(f"[DRY] slice {i+1}/{slices} {side}/{pos_side} sz={cur_sz} px={px}")
            else:
                try:
                    resp=bot.client.place_order(instId=bot.cfg.inst_id, tdMode=bot.cfg.td_mode, side=side, posSide=pos_side,
                                                ordType="limit", sz=str(cur_sz), px=f"{px:.2f}", reduceOnly=False, clOrdId=clid)
                    order_ids.append(resp.get("ordId", resp))
                except Exception as e:
                    print("[SLICER] place error:", e)
            await asyncio.sleep(self.slice_timeout_s)
            sz_left -= cur_sz
        return order_ids
