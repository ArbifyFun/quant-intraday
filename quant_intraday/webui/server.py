
import os, time, json, pathlib, asyncio, glob
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Depends, HTTPException, status, Form, Body, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

# optional template engine
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape  # type: ignore
except Exception:  # pragma: no cover
    Environment = FileSystemLoader = select_autoescape = None

LIVE_DIR = os.getenv("QI_LOG_DIR", "live_output")
TOKEN = os.getenv("QI_WEB_TOKEN", None)
BASIC_USER = os.getenv("QI_WEB_BASIC_USER", None)
BASIC_PASS = os.getenv("QI_WEB_BASIC_PASS", None)

STATIC_DIR = pathlib.Path(__file__).parent / "static"
TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Quant Intraday WebUI", version="0.22.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

def get_env():
    return {"live_dir": str(LIVE_DIR), "token": bool(TOKEN)}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    if Environment and FileSystemLoader:
        env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=select_autoescape())
        tpl_path = TEMPLATES_DIR / "index.html"
        if tpl_path.exists():
            tpl = env.get_template("index.html")
            return HTMLResponse(tpl.render(info=get_env()))
    # fallback
    return HTMLResponse("<h1>Quant Intraday WebUI</h1><p>Server online.</p>")

# health
@app.get("/healthz")
async def healthz():
    return {"ok": True, "live_dir": str(LIVE_DIR)}
            
            # Simple stats endpoint
@app.get("/stats", response_class=JSONResponse)
async def stats():
    """
    Return the latest equity, drawdown and trade count.

    This endpoint reads ``equity.csv`` and any ``trades_*.csv`` files from
    the current ``LIVE_DIR`` directory and returns a JSON object with
    the latest metrics.  Frontend dashboards or scripts may poll this
    endpoint to obtain real-time status without parsing log files directly.
    """
    import pandas as pd, glob
    eq_p = os.path.join(LIVE_DIR, "equity.csv")
    eq = None
    dd = None
    if os.path.exists(eq_p):
        try:
            df = pd.read_csv(eq_p)
            if len(df) > 0:
                eq = float(df.iloc[-1, 1])
                s = pd.Series(df.iloc[:, 1])
                dd = float((s / s.cummax() - 1.0).iloc[-1])
        except Exception:
            pass
    trades = 0
    for f in glob.glob(os.path.join(LIVE_DIR, "trades_*.csv")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                trades += max(sum(1 for _ in fh) - 1, 0)
        except Exception:
            pass
    return {"equity": eq, "drawdown": dd, "trades": trades}

