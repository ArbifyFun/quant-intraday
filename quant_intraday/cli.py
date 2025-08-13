import os
try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass
import os, sys, asyncio, typer
from rich import print as rprint
from .config import load_qi_config
from .utils import logger as qi_logger
from .engine.exchange.okx_client import OKXClient  # dual path ensured in v18
from .engine.live_bot import RunConfig, Bot
from .engine.portfolio import PortfolioOrchestrator

app = typer.Typer(help="Quant Intraday unified CLI")

@app.command()
def version():
    rprint("[bold green]quant-intraday v0.19.0[/]")

@app.command()
def preflight():
    """Run environment & connectivity checks and write live_output/preflight.json"""
    import quant_intraday.scripts.preflight as pre  # type: ignore
    pre.main()

@app.command()
def init():
    """Generate sample qi.yaml / portfolio.yaml / calendar.yaml if missing"""
    import pathlib
    from importlib import resources

    root = pathlib.Path(".")
    for fn in ("qi.yaml", "portfolio.yaml", "calendar.yaml"):
        dst = root / fn
        if dst.exists():
            continue
        try:
            with resources.files("quant_intraday.templates").joinpath(fn).open("rb") as src:
                dst.write_bytes(src.read())
            rprint(f"[cyan]created {fn} from template[/]")
        except FileNotFoundError:
            dst.write_text("", encoding="utf-8")
            rprint(f"[yellow]template {fn} missing; created empty file[/]")
    rprint("[green]init done.[/]")

@app.command()
def live(inst: str, tf: str = "5m", strategy: str = "auto", exec_mode: str = "autoexec", live: bool = True):
    """Run single-instrument live bot (reads env for keys)."""
    cli = OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    cfg = RunConfig(inst_id=inst, tf=tf, live=live, td_mode="cross")
    b = Bot(cfg, cli)
    b.cfg.exec_mode = exec_mode
    asyncio.run(b.run())

@app.command()
def multi(cfg: str = "portfolio.yaml", risk: float = 0.007, dd: float = 0.08):
    """Run portfolio orchestrator (multi-instrument)."""
    cli = OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    orch = PortfolioOrchestrator(cli, cfg_path=cfg, risk_pct=risk, dd_limit=dd)
    asyncio.run(orch.run())

@app.command()
def run(cfg: str = "qi.yaml"):
    """Run from master config (qi.yaml)."""
    q = load_qi_config(cfg)
    # prefer portfolio orchestrator
    # OKXClient does not accept a ``simulated`` keyword argument.  Simulation
    # mode is controlled via the ``OKX_SIMULATED`` environment variable
    # instead (see ``exchange/okx_client.py``).  Pass only the required
    # parameters here.
    cli = OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    # write portfolio.yaml from qi.yaml for compatibility
    import yaml, json
    pf = {"instruments": [ {"inst": it.inst, "tf": it.tf, "risk_share": it.risk_share, "exec_mode": q.execution.mode} for it in q.portfolio.instruments ],
          "risk_pct": q.risk.risk_pct, "dd_limit": q.risk.dd_limit }
    with open("portfolio.yaml","w",encoding="utf-8") as f: yaml.safe_dump(pf, f, allow_unicode=True)
    orch = PortfolioOrchestrator(cli, cfg_path="portfolio.yaml", risk_pct=q.risk.risk_pct, dd_limit=q.risk.dd_limit)
    asyncio.run(orch.run())

@app.command()
def backtest(csv: str, strategy: str = "auto", inst: str = None, exec_mode: str = "kyle", kyle_lambda: float = 0.0):
    """Run backtest with execution model."""
    from .backtest.engine import Backtester, RiskParams
    import pandas as pd
    df = pd.read_csv(csv, parse_dates=["dt"]).set_index("dt")
    bt = Backtester(strategy=strategy, risk=RiskParams(), exec_mode=exec_mode, kyle_lambda=kyle_lambda)
    res = bt.backtest(df)
    rprint(res["summary"])

@app.command()
def autopilot():
    """Run weights/cooling/thresholds + Kelly scaler."""
    import quant_intraday.scripts.autopilot_plus as ap  # type: ignore
    import quant_intraday.scripts.kelly_scaler as ks   # type: ignore
    import quant_intraday.scripts.rebalance as rb      # type: ignore
    ap.main(); ks.main(); rb.main()

@app.command()
def metrics():
    """Start Prometheus exporter on :9000"""
    import quant_intraday.scripts.metrics_exporter as me  # type: ignore
    me.main()

@app.command()
def replay():
    """Generate execution replay HTML from execlog + fills-history."""
    import quant_intraday.scripts.exec_replay as rp  # type: ignore
    rp.main()

@app.command()
def fetch_fb(inst: str = "BTC-USDT-SWAP", fut: str = "BTC-USDT-240927", out: str = "fb_history.csv"):
    """Fetch funding/basis history to CSV."""
    import quant_intraday.scripts.fetch_okx_funding_basis as fb  # type: ignore
    fb.main(inst, fut, out)

@app.command()
def dashboard(
    live_dir: str = typer.Option(None, help="实时数据目录，默认使用 QI_LOG_DIR"),
    refresh: float = typer.Option(1.0, help="刷新间隔（秒）"),
    trades_limit: int = typer.Option(5, help="最近成交显示条数"),
):
    """启动终端实时看板，展示权益、执行指标、仓位、信号与成交。"""
    import quant_intraday.scripts.terminal_dashboard as td  # type: ignore

    td.main(live_dir or os.getenv("QI_LOG_DIR", "live_output"), refresh, trades_limit)

if __name__ == "__main__":
    app()

@app.command()
def doctor(cfg: str = "qi.yaml"):
    """Validate qi.yaml, run preflight, and print a concise health report."""
    qi_logger.maybe_enable()
    from quant_intraday.scripts.preflight import main as pre  # type: ignore
    ok=True
    try:
        q = load_qi_config(cfg)
        rprint("[green]✓ qi.yaml valid[/]")
    except Exception as e:
        ok=False; rprint(f"[red]✗ qi.yaml invalid:[/] {e}")
    try:
        pre()
        rprint("[green]✓ preflight passed (see live_output/preflight.json)[/]")
    except SystemExit as se:
        if int(getattr(se, "code", 1)) != 0:
            ok=False; rprint("[red]✗ preflight failed[/]")
    except Exception as e:
        ok=False; rprint(f"[red]✗ preflight error:[/] {e}")
    raise SystemExit(0 if ok else 2)

@app.command()
def completions(shell: str = "bash"):
    """Print shell completion snippet for qi (bash|zsh|fish)."""
    import typer
    from typer.main import get_completion_inspect_parameters
    # Typer doesn't expose generator directly; provide simple instructions
    if shell not in ("bash","zsh","fish"):
        rprint("[yellow]Supported shells: bash|zsh|fish[/]"); raise SystemExit(1)
    rprint(f"# Add the following to your {shell} rc file:")
    rprint("eval \"$(_QI_COMPLETE="+shell+"_source qi)\"")

@app.command()
def grafana_export(out: str = "grafana/dashboard_quant_intraday.json"):
    """Write sample Grafana dashboard JSON (for Prometheus metrics)."""
    import os, json
    os.makedirs(os.path.dirname(out), exist_ok=True)
    dash = {
      "title": "Quant Intraday",
      "panels": [
        {"type":"graph","title":"Equity","targets":[{"expr":"qi_equity"}]},
        {"type":"graph","title":"PnL","targets":[{"expr":"qi_pnl"}]},
        {"type":"graph","title":"Cancel Ratio","targets":[{"expr":"qi_cancel_ratio"}]},
        {"type":"graph","title":"Queue Pos (est)","targets":[{"expr":"qi_queue_pos_est"}]},
      ],
      "schemaVersion": 27, "version": 1
    }
    open(out,"w").write(json.dumps(dash, indent=2))
    rprint(f"[green]wrote {out}[/]")

@app.command()
def prom_rules(out: str = "prometheus/alerts.yml"):
    """Write sample Prometheus alert rules."""
    import os
    os.makedirs(os.path.dirname(out), exist_ok=True)
    rules = """
groups:
- name: quant-intraday
  rules:
  - alert: BotDown
    expr: absent(qi_exec_fill_all) or absent(qi_equity)
    for: 15m
    labels: {severity: critical}
    annotations: {summary: "No metrics from bot for 15m."}
  - alert: HighCancelRatio
    expr: qi_cancel_ratio > 3
    for: 10m
    labels: {severity: warning}
    annotations: {summary: "Cancel ratio high >3 for 10m."}
  - alert: Drawdown
    expr: min_over_time(qi_equity[1d]) / max_over_time(qi_equity[1d]) < 0.92
    for: 5m
    labels: {severity: warning}
    annotations: {summary: "1d drawdown >8%."}
"""
    open(out,"w").write(rules)
    rprint(f"[green]wrote {out}[/]")

@app.command()
def web(host: str = "0.0.0.0", port: int = 8080):
    """Start Web UI (FastAPI). Auth: Bearer $QI_WEB_TOKEN (optional)."""
    import uvicorn
    uvicorn.run("quant_intraday.webui.server:app", host=host, port=port, reload=False)

@app.command()
def push():
    """Start OKX private push listener (orders channel)."""
    import quant_intraday.scripts.push_listener as pl  # type: ignore
    pl.main()

@app.command()
def kpi():
    """Start the execution KPI daemon (reads execlog.csv and exposes KPIs as JSON)."""
    # Delegate to the KPI daemon script; unify previous definitions.
    from quant_intraday.scripts import exec_kpi_daemon  # type: ignore
    exec_kpi_daemon.main()


@app.command()
def check():
    """Aggregate health check: preflight + doctor"""
    try:
        import quant_intraday.scripts.preflight as pre  # type: ignore
        pre.main()
    except Exception as e:
        print("preflight error:", e)
    try:
        doctor()
    except Exception as e:
        print("doctor error:", e)


@app.command(name="module-info")
def module_info():
    """Print loaded module paths and selected Bot class attributes for debugging."""
    import importlib, quant_intraday
    from rich import print as rprint
    rprint({"pkg_file": quant_intraday.__file__})
    try:
        lb = importlib.import_module("quant_intraday.engine.live_bot")
        rprint({"live_bot_file": lb.__file__})
        has = {"_wss_urls": hasattr(lb.Bot, "_wss_urls"),
               "_ws_proxy": hasattr(lb.Bot, "_ws_proxy")}
        rprint({"bot_attrs": has})
        if has["_wss_urls"]:
            rprint({"_wss_urls_preview": str(lb.Bot._wss_urls)})
    except Exception as e:
        rprint({"module_info_error": str(e)})


@app.command()
def env():
    """Print effective OKX/QI environment (secrets masked)."""
    from dotenv import dotenv_values, find_dotenv
    import os, json
    cfg_path = find_dotenv(usecwd=True) or ".env"
    file_vars = dotenv_values(cfg_path) if cfg_path else {}
    def mask(v):
        if not v: return v
        if len(v)<=6: return "*"*len(v)
        return v[:3] + "*"*(len(v)-6) + v[-3:]
    keys = ["OKX_API_KEY","OKX_API_SECRET","OKX_API_PASSPHRASE","OKX_SIMULATED","OKX_DEMO_BROKER_ID",
            "QI_PROXY_MODE","QI_HTTP_PROXY","QI_HTTPS_PROXY","QI_WS_PROXY"]
    effective = {k: (os.getenv(k) or file_vars.get(k)) for k in keys}
    masked = {k: (mask(v) if k in ("OKX_API_KEY","OKX_API_SECRET","OKX_API_PASSPHRASE") else v) for k,v in effective.items()}
    print(json.dumps({"cwd": os.getcwd(), "dotenv": cfg_path, "env": masked}, ensure_ascii=False, indent=2))


@app.command(name='http-test')
def http_test(sim: bool = True):
    """One-shot GET /account/balance with debug prints (masking secrets)."""
    import os, json
    from quant_intraday.engine.exchange.okx_client import OKXClient
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True), override=False)
    key = os.getenv("OKX_API_KEY"); sec = os.getenv("OKX_API_SECRET"); pp = os.getenv("OKX_API_PASSPHRASE")
    if not all([key,sec,pp]):
        print("! Missing OKX env in .env or shell (key/secret/passphrase)."); return
    if sim:
        os.environ["OKX_SIMULATED"] = "1"
    cli = OKXClient(key, sec, pp, account=os.getenv("OKX_ACCOUNT","trade"))
    try:
        # also print time drift
        srv = cli.server_time_ms()
        import time
        loc = int(time.time()*1000)
        print("[OKX][DBG] time_drift_ms", srv - loc)
    except Exception as e:
        print("[OKX][DBG] time endpoint error", e)
    try:
        path = "/api/v5/account/balance"
        r = cli.rest.get(path, headers=cli._headers("GET", path, ""))
        print("[OKX][DBG] status", r.status_code)
        print("[OKX][DBG] text", r.text[:400])
    except Exception as e:
        print("http-test error:", repr(e))
