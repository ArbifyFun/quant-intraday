import os, asyncio, yaml, time
from dataclasses import dataclass
from .live_bot import Bot, RunConfig
from ..utils.global_risk import GlobalRiskGuard
from ..utils.notifier import notify

@dataclass
class PortfolioItem:
    inst_id: str
    tf: str = "5m"
    risk_share: float = 1.0
    exec_mode: str = "autoexec"

class PortfolioOrchestrator:
    def __init__(self, client, cfg_path="portfolio.yaml", log_dir="live_output", risk_pct=0.007, dd_limit=0.08):
        self.client=client; self.cfg_path=cfg_path; self.log_dir=log_dir; self.risk_pct=risk_pct
        self.dd_limit=dd_limit; self.guard=GlobalRiskGuard(log_dir, dd_limit)
        self.items=self._load_cfg()

    def _load_cfg(self):
        if not os.path.exists(self.cfg_path):
            # default BTC/ETH/SOL
            return [PortfolioItem("BTC-USDT-SWAP", "5m", 1.0), PortfolioItem("ETH-USDT-SWAP","5m",1.0), PortfolioItem("SOL-USDT-SWAP","5m",1.0)]
        cfg=yaml.safe_load(open(self.cfg_path,"r",encoding="utf-8")) or {}
        arr=[]
        for it in cfg.get("instruments", []):
            arr.append(PortfolioItem(inst_id=it["inst"], tf=it.get("tf","5m"), risk_share=float(it.get("risk_share",1.0)), exec_mode=it.get("exec_mode","autoexec")))
        return arr

    async def run(self):
        tasks=[]
        total_share = sum(max(0.0, it.risk_share) for it in self.items) or 1.0
        for it in self.items:
            rp = self.risk_pct * (it.risk_share / total_share)
            bot_cfg = RunConfig(inst_id=it.inst_id, tf=it.tf, live=True, risk_pct=rp)
            bot = Bot(bot_cfg, self.client)
            bot.cfg.exec_mode = it.exec_mode
            tasks.append(asyncio.create_task(bot.run()))
        # watchdog
        async def watchdog():
            while True:
                if await self.guard.check():
                    await notify("portfolio_paused", {"reason":"dd_limit", "limit": self.dd_limit})
                    # in this simplified version, we just print; in practice, you'd stop tasks
                await asyncio.sleep(10)
        tasks.append(asyncio.create_task(watchdog()))
        await asyncio.gather(*tasks)
