import os
import glob
import time
import pandas as pd


def monitor_live_output(live_dir: str = "live_output", interval: float = 5.0, once: bool = False):
    """
    Display live equity, drawdown and trade count from the live output directory.

    Args:
        live_dir: Directory where equity.csv and trades_*.csv are stored.
        interval: Refresh interval in seconds.
        once: If True, print once and exit.
    """
    while True:
        try:
            eq_path = os.path.join(live_dir, "equity.csv")
            equity = None
            drawdown = None
            if os.path.exists(eq_path):
                try:
                    df = pd.read_csv(eq_path)
                    if len(df) > 0:
                        last = df.iloc[-1]
                        equity = float(last.get("equity", last.iloc[-1]))
                        if "equity" in df.columns and equity is not None:
                            peak = df["equity"].max()
                            if peak != 0:
                                drawdown = (equity - peak) / peak
                            else:
                                drawdown = 0.0
                except Exception:
                    pass
            trades = 0
            for fp in glob.glob(os.path.join(live_dir, "trades_*.csv")):
                try:
                    tdf = pd.read_csv(fp)
                    trades += len(tdf)
                except Exception:
                    continue
            if equity is not None:
                print(f"[MONITOR] equity={equity:.2f} drawdown={drawdown:.4f} trades={trades}")
            else:
                print(f"[MONITOR] equity=N/A drawdown=N/A trades={trades}")
        except Exception as e:
            print(f"[MONITOR] error: {e}")
        if once:
            break
        time.sleep(interval)
