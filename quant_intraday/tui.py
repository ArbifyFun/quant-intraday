"""
Terminal UI module using rich to display live metrics.

This module defines a `run_tui` function that uses the `rich` library to
periodically query live metrics (equity, drawdown, trades) and display them
in a dynamic table.
"""

import time
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.live import Live

from .monitor import get_metrics


def run_tui(live_dir: str = "live_output", interval: float = 2.0) -> None:
    """
    Run a terminal UI to display live equity, drawdown and trade count.

    :param live_dir: Directory where live output files (equity.csv, trades_*.csv) reside.
    :param interval: Refresh interval in seconds for updating the display.
    """
    console = Console()
    # prepare a table with two columns: Metric and Value
    table = Table(title="Quant Intraday Live Metrics")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    # Use Live to continuously update the table.
    # refresh_per_second controls how often the screen refreshes automatically.
    refresh_rate = 1  # at least 1 refresh per second
    with Live(table, console=console, refresh_per_second=refresh_rate) as live:
        while True:
            metrics = get_metrics(live_dir)
            equity = metrics.get("equity")
            drawdown = metrics.get("drawdown")
            trades = metrics.get("trades")

            # Clear any existing rows
            table.rows.clear()
            if equity is not None:
                table.add_row("Equity", f"{equity:,.2f}")
            if drawdown is not None:
                # Format drawdown as percentage if it's a fractional value
                formatted_dd = (
                    f"{drawdown * 100:.2f}%" if isinstance(drawdown, float) and drawdown < 1 else str(drawdown)
                )
                table.add_row("Drawdown", formatted_dd)
            if trades is not None:
                table.add_row("Trades", str(trades))
            # Update the live display
            live.update(table)
            # Sleep until next refresh
            time.sleep(interval)
