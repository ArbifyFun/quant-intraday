import asyncio, time, os

class LOBExecutor:
    """
    Event-driven cancel/replace based on books5 events.
    Signals:
      - Spread widen/narrow beyond thresholds
      - Imbalance flips beyond +/-imb_th
      - Best queue size surge
    Throttles:
      - min_dwell_s: min lifetime before cancel/replace
      - max_cancels_per_min: cap cancel rate
    """
    def __init__(self, widen_ticks:int=3, narrow_ticks:int=1, imb_th:float=0.2, queue_surge:float=8000,
                 min_dwell_s:int=2, max_cancels_per_min:int=20):
        self.widen_ticks=widen_ticks; self.narrow_ticks=narrow_ticks
        self.imb_th=imb_th; self.queue_surge=queue_surge
        self.min_dwell_s=min_dwell_s; self.max_cpm=max_cancels_per_min
        self._cxl_hist=[]  # timestamps

    def _can_cancel(self):
        now=time.time()
        self._cxl_hist=[t for t in self._cxl_hist if now - t < 60]
        if len(self._cxl_hist) >= self.max_cpm: return False
        self._cxl_hist.append(now); return True

    def _snapshot(self, bot):
        b=bot._books
        if not b: return None
        bids=b.get("bids",[]); asks=b.get("asks",[])
        if not bids or not asks: return None
        bid_px, bid_q = float(bids[0][0]), float(bids[0][1])
        ask_px, ask_q = float(asks[0][0]), float(asks[0][1])
        spread = ask_px - bid_px
        mid = (ask_px + bid_px)/2.0
        imb = (bid_q - ask_q) / max(1e-9, (bid_q + ask_q))
        return dict(bid=bid_px, ask=ask_px, spread=spread, mid=mid, imb=imb, bid_q=bid_q, ask_q=ask_q)

    async def execute(self, bot, side: str, pos_side: str, total_sz: int, px_hint: float):
        """
        Place and manage a limit order at the top of book using a simple LOB (limit‑order book) executor.

        This implementation tracks the best bid/ask via ``_snapshot`` and cancels/reposts when either the
        spread widens, the book imbalance turns adverse, the queue size surges or the spread narrows.  To
        prevent runaway cancellations, a per‑minute budget is enforced via ``_can_cancel``.  Orders are
        always posted at integer multiples of the instrument's tick size.

        Parameters
        ----------
        bot : object
            Trading bot instance exposing ``_books``, ``_costs``, ``_log_dir``, ``_round_px`` and client.
        side : str
            Order side ('buy' or 'sell').
        pos_side : str
            Position side ('long' or 'short').  This is passed through to the exchange API.
        total_sz : int
            Total size to place.  If ``total_sz`` is non‑positive, the function returns immediately.
        px_hint : float
            Price hint used when there is no book snapshot available.

        Returns
        -------
        list
            List of client or exchange order IDs placed during the execution cycle.
        """
        # normalise size
        tsz = int(total_sz)
        if tsz <= 0:
            return []
        # tick size for price adjustments; fall back to 1 if unavailable
        try:
            ticks = bot._costs.tick_size
        except Exception:
            ticks = getattr(bot, "tick_size", 1.0)
        ids: list = []
        # place initial near best bid/ask
        snap = self._snapshot(bot)
        if not snap:
            # when books not ready, use hint via helper
            price = bot._book_limit_px("buy" if pos_side == "long" else "sell", px_hint)
        else:
            price = snap["bid"] if side == "buy" else snap["ask"]
        price = bot._round_px(price)
        clid = f"lob_{int(time.time())}_0"
        placed_time: float
        # Dry‑run mode (not live) writes execlog and uses synthetic order IDs
        if not bot.cfg.live:
            with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                f.write(
                    f"{int(time.time()*1000)},LOB_PLACE,{bot.cfg.inst_id},{side},{pos_side},{tsz},{price:.6f}\n"
                )
            ids.append(clid)
            placed_time = time.time()
        else:
            resp = bot.client.place_order(
                instId=bot.cfg.inst_id,
                tdMode=bot.cfg.td_mode,
                side=side,
                posSide=pos_side,
                ordType="limit",
                sz=str(tsz),
                px=f"{price:.6f}",
                reduceOnly=False,
                clOrdId=clid,
            )
            ord_id = resp.get("ordId", resp)
            ids.append(ord_id)
            placed_time = time.time()
        last_snap = snap or self._snapshot(bot) or {}
        # event loop: monitor books and decide whether to repost
        while True:
            await asyncio.sleep(0.3)
            s = self._snapshot(bot)
            if not s:
                continue
            # compute triggers
            spread_ticks = s["spread"] / (ticks or 1.0)
            surge = (s["ask_q"] if side == "buy" else s["bid_q"]) > self.queue_surge
            imb_bad = (
                s["imb"] < -self.imb_th if side == "buy" else s["imb"] > self.imb_th
            )
            narrow = spread_ticks <= self.narrow_ticks
            widen = spread_ticks >= self.widen_ticks
            dwell_ok = (time.time() - placed_time) >= self.min_dwell_s
            if (widen or imb_bad or surge or narrow) and dwell_ok:
                if not self._can_cancel():
                    continue
                # cancel & repost at adjusted price
                adj = (1 if side == "buy" else -1) * (1 if narrow else -1)  # if narrow -> be more aggressive
                new_px = s["bid"] if side == "buy" else s["ask"]
                new_px = new_px + adj * (ticks or 1.0)
                new_px = bot._round_px(new_px)
                if not bot.cfg.live:
                    with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                        f.write(
                            f"{int(time.time()*1000)},LOB_REPOST,{bot.cfg.inst_id},{side},{pos_side},{tsz},{new_px:.6f}\n"
                        )
                    placed_time = time.time()
                    last_snap = s
                    continue
                try:
                    # best‑effort: repost; private WS should handle cancellation detection
                    resp = bot.client.place_order(
                        instId=bot.cfg.inst_id,
                        tdMode=bot.cfg.td_mode,
                        side=side,
                        posSide=pos_side,
                        ordType="limit",
                        sz=str(tsz),
                        px=f"{new_px:.6f}",
                        reduceOnly=False,
                        clOrdId=f"lob_{int(time.time())}",
                    )
                    ids.append(resp.get("ordId", resp))
                    placed_time = time.time()
                    last_snap = s
                    with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                        f.write(
                            f"{int(time.time()*1000)},LOB_REPOST,{bot.cfg.inst_id},{side},{pos_side},{tsz},{new_px:.6f}\n"
                        )
                except Exception:
                    with open(os.path.join(bot._log_dir, "execlog.csv"), "a", encoding="utf-8") as f:
                        f.write(
                            f"{int(time.time()*1000)},LOB_REPOST_FAIL,{bot.cfg.inst_id},{side},{pos_side},{tsz},{new_px:.6f}\n"
                        )
            last_snap = s
            # break condition: after 30 seconds bail out; in live this should be replaced by fill tracking
            if time.time() - placed_time > 30:
                break
        return ids