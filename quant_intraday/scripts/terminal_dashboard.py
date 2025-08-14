#!/usr/bin/env python3
"""终端实时看板，用于监控账户权益、执行指标、仓位、信号与成交。

该脚本读取 ``live_output`` 下的 ``equity.csv``、``exec_kpis.json``、
``positions.json``、``signals.json`` 与 ``trades.csv``，并以 Rich 布局实时
刷新展示，适合在服务器终端持续运行。看板时间戳统一显示为 UTC。
"""

from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, TypeVar

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

LIVE_DIR = os.getenv("QI_LOG_DIR", "live_output")


def _read_equity(path: str) -> Optional[Tuple[float, float]]:
    """读取最新权益与回撤。

    返回 ``(equity, drawdown)``；若文件缺失或解析失败则返回 ``None``。
    """

    if not os.path.exists(path):
        return None
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            return None
        last = float(rows[-1]["equity"])
        max_eq = max(float(r["equity"]) for r in rows)
        dd = (last / max_eq - 1.0) if max_eq else 0.0
        return last, dd
    except Exception:
        return None


T = TypeVar("T")


def _load_json(path: str, key: str, default: T) -> T:
    """读取 JSON 文件并返回指定键，异常时返回默认值。"""

    try:
        with open(path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = json.load(f)
        return data.get(key, default)
    except Exception:
        return default


def _read_kpis(path: str) -> Dict[str, Dict[str, float]]:
    """读取执行 KPI JSON。"""

    return _load_json(path, "by_inst", {})


def _read_positions(path: str) -> List[Dict[str, float]]:
    """读取仓位信息。"""

    return _load_json(path, "positions", [])


def _read_signals(path: str) -> List[Dict[str, str]]:
    """读取最新交易信号。"""

    return _load_json(path, "signals", [])


def _read_trades(path: str, limit: int = 5) -> List[Dict[str, str]]:
    """读取最近成交记录。"""

    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows = rows[-limit:]
        for r in rows:
            ts = r.get("ts")
            if ts:
                try:
                    r["time"] = datetime.fromtimestamp(float(ts) / 1000, tz=timezone.utc).strftime("%H:%M:%S")
                except Exception:
                    r["time"] = "-"
        return rows
    except Exception:
        return []


def _build_equity_panel(eq: Optional[Tuple[float, float]]) -> Panel:
    if not eq:
        body = Text("无权益数据", style="yellow", justify="center")
        return Panel(body, title="权益", border_style="red")
    equity, dd = eq
    body = Text.assemble(
        (f"{equity:.2f}\n", "bold green"),
        (f"回撤: {dd * 100:.2f}%", "red"),
    )
    return Panel(body, title="权益", border_style="green")


def _build_kpi_panel(kpis: Dict[str, Dict[str, float]]) -> Panel:
    table = Table(expand=True)
    table.add_column("品种")
    table.add_column("成交率", justify="right")
    table.add_column("撤单比", justify="right")
    table.add_column("寿命p50(ms)", justify="right")
    table.add_column("寿命p90(ms)", justify="right")

    for inst, m in kpis.items():
        fr = m.get("fill_rate", 0.0)
        cr = m.get("cancel_ratio", 0.0)
        fr_style = "green" if fr > 0.8 else "yellow" if fr > 0.5 else "red"
        cr_style = "red" if cr > 0.5 else "green"
        table.add_row(
            inst,
            f"[{fr_style}]{fr:.2f}[/{fr_style}]",
            f"[{cr_style}]{cr:.2f}[/{cr_style}]",
            f"{m.get('lifetime_p50_ms', 0):.0f}",
            f"{m.get('lifetime_p90_ms', 0):.0f}",
        )

    subtitle = datetime.now(timezone.utc).strftime("UTC %H:%M:%S")
    return Panel(table, title="执行 KPI", subtitle=subtitle, border_style="cyan")


def _build_positions_panel(positions: List[Dict[str, float]]) -> Panel:
    table = Table(expand=True)
    table.add_column("品种")
    table.add_column("持仓", justify="right")
    table.add_column("盈亏", justify="right")

    for pos in positions:
        pnl = pos.get("pnl", 0.0)
        pnl_style = "green" if pnl >= 0 else "red"
        table.add_row(
            pos.get("inst", "-"),
            f"{pos.get('qty', 0):.4f}",
            f"[{pnl_style}]{pnl:.2f}[/{pnl_style}]",
        )

    return Panel(table, title="仓位", border_style="magenta")


def _build_signals_panel(signals: List[Dict[str, str]]) -> Panel:
    table = Table(expand=True)
    table.add_column("品种")
    table.add_column("信号")
    table.add_column("强度", justify="right")

    for sig in signals:
        table.add_row(
            sig.get("inst", "-"),
            sig.get("signal", "-"),
            f"{sig.get('score', 0):.2f}",
        )

    return Panel(table, title="信号", border_style="yellow")


def _build_trades_panel(trades: List[Dict[str, str]]) -> Panel:
    table = Table(expand=True)
    table.add_column("时间")
    table.add_column("品种")
    table.add_column("方向")
    table.add_column("价格", justify="right")
    table.add_column("数量", justify="right")

    for tr in trades:
        side = tr.get("side", "-")
        side_l = str(side).lower()
        side_style = "green" if side_l in ("buy", "long") else "red" if side_l in ("sell", "short") else "white"
        table.add_row(
            tr.get("time", "-"),
            tr.get("inst", "-"),
            f"[{side_style}]{side}[/{side_style}]",
            tr.get("price", "-"),
            tr.get("qty", "-"),
        )

    return Panel(table, title="最近成交", border_style="blue")


def _refresh(layout: Layout, live_dir: str, trades_limit: int) -> None:
    eq = _read_equity(os.path.join(live_dir, "equity.csv"))
    kpis = _read_kpis(os.path.join(live_dir, "exec_kpis.json"))
    positions = _read_positions(os.path.join(live_dir, "positions.json"))
    signals = _read_signals(os.path.join(live_dir, "signals.json"))
    trades = _read_trades(os.path.join(live_dir, "trades.csv"), limit=trades_limit)

    layout["header"].update(_build_equity_panel(eq))
    layout["kpi"].update(_build_kpi_panel(kpis))
    layout["positions"].update(_build_positions_panel(positions))
    layout["signals"].update(_build_signals_panel(signals))
    layout["trades"].update(_build_trades_panel(trades))


def _init_layout() -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
    )
    layout["main"].split_row(
        Layout(name="kpi"),
        Layout(name="side"),
    )
    layout["side"].split_column(
        Layout(name="positions", size=6),
        Layout(name="signals", size=6),
        Layout(name="trades"),
    )
    return layout


def main(live_dir: str = LIVE_DIR, refresh: float = 1.0, trades_limit: int = 5) -> None:
    """启动终端实时看板。"""

    layout = _init_layout()
    with Live(layout, refresh_per_second=4, screen=True):
        while True:
            _refresh(layout, live_dir, trades_limit)
            time.sleep(refresh)


if __name__ == "__main__":  # pragma: no cover - 脚本入口
    main()

