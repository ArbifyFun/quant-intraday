"""
Terminal UI module using rich to display live metrics with change indicators.

This module defines a 'run_tui' function that uses the 'rich' library
to periodically query live metrics (equity, drawdown, trades) and display them
in a dynamic table. It also calculates changes relative to the previous refresh
and uses colored arrows to indicate the direction of change.

Press 'p' to panic flatten (close all positions), press 'q' to quit the TUI, and press 'h' or '?' to show help.
"""
import time
import sys
import s
from rich.console import Console
from rich.table import Table
from rich.live import Live

from .monitor import get_metrics

def run_tui(live_dir: str = "live_output", interval: float = 2.0) -> None:
    """
      """
    Run a terminal UI to display live equity, drawdown and trade count with change indicators.

  

    :param live_dir: Directory where live output files (equity.csv, trades-*.csv) reside.
    :param interval: Refresh interval in seconds for updating the display.
    """
    console = Console()
    table = Table(title="Quant Intraday Live Metrics")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    # Previous values for computing deltas
    prev_equity: Optional[float] = None
    prev_drawdown: Optional[float] = None
    prev_trades: Optional[int] = None

    
    # Determine refresh rate for Live (at least 1)
    refresh_rate = max(1, int(1 / interval)) if interval > 0 else 1

    with Live(table, console=console, refresh_per_second=refresh_rate):

        

        while True:
            metrics = get_metrics(live_dir)
            equity = metrics.get("equity")
            drawdown = metrics.get("drawdown")
            trades = metrics.get("trades")

            # Prepare rows with color-coded change indicators
            rows = []

            # Equity row
            if equity is not None:
                if prev_equity is None:
                    eq_display = f"{equity:.2f}"
                else:
     
                    delta = equity - prev_equity
                    if delta > 0:
                        arrow = "\u25B2"
                        color = "green"
                    elif delta < 0:
                        arrow = "\u25BC"
                        color = "red"
                    else:
                        arrow = "\u2192"
                        color = "white"
                    eq_display = f"{equity:.2f} [bold {color}]{arrow}{delta:+.2f}[/]"
                rows.append(("Equity", eq_display))
                prev_equity = equity

            # Drawdown row (percentage)
            if drawdown is not None:
                if prev_drawdown is None:
                    if isinstance(drawdown, float):
                        dd_display = f"{drawdown * 100:.2f}%"
                    else:
                        dd_display = str(drawdown)
                else:
                    if isinstance(drawdown, float) and isinstance(prev_drawdown, float):
                        delta_pct = (drawdown - prev_drawdown) * 100
                        if delta_pct > 0:
                            arrow = "\u25B2"
                            color = "red"
                        elif delta_pct < 0:
                            arrow = "\u25BC"
                            color = "green"
                        else:
                            arrow = "\u2192"
                            color = "white"
                        dd_display = f"{drawdown * 100:.2f}% [bold {color}]{arrow}{delta_pct:+.2f}[/]"
                    else:
                        dd_display = str(drawdown)
                rows.append(("Drawdown", dd_display))
                prev_drawdown = drawdown

            # Trades row
            if trades is not None:
                if prev_trades is None:
                    tr_display = str(trades)
                else:
                    delta = trades - prev_trades
                    if delta > 0:
                        arrow = "\u25B2"
                        color = "green"
                    elif delta < 0:
                        arrow = "\u25BC"
                        color = "red"
                    else:
                        arrow = "\u2192"
                        color = "white"
                    tr_display = f"{trades} [bold {color}]{arrow}{delta:+}[/]"
                rows.append(("Trades", tr_display))
                prev_trades = trades

            # Clear table and add updated rows
            table.rows.clear()
            for label, value in rows:
                table.add_row(label, value)
    # Check for user input commands
    if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
        cmd = sys.stdin.read(1).strip().lower()
        if cmd == "p":
            try:
                from quant_intraday.scripts.panic_flatten import main as panic_flatten_main
                panic_flatten_main()
            except Exception as e:
                console.print(f"[red]Error during panic flatten: {e}[/]")
        elif cmd == "q":
            break
        elif cmd == "h" or cmd == "?":
            console.print("\nCommands: p = panic flatten, q = quit, h/? = help")
      
   
            # Sleep until next refresh
            time.sleep(interval)
