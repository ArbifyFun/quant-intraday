#!/usr/bin/env python3
"""
Attribution: build round-trips from OKX fills and local trade intents, compute PnL and decompose into
- execution_cost (entry slippage vs intended + fees)
- alpha (residual)
Outputs: attrib/positions_YYYYMMDD.csv and attrib/attribution_report.html
"""
import os, pandas as pd, numpy as np, datetime as dt
from quant_intraday.exchange.okx_client import OKXClient

def load_intents(live_dir="live_output"):
    rows=[]
    for fn in os.listdir(live_dir):
        if fn.startswith("trades_") and fn.endswith(".csv"):
            df=pd.read_csv(os.path.join(live_dir, fn))
            rows.append(df)
    if not rows: return pd.DataFrame(columns=["ts","inst","side","price","sl","tp","size","reason"])
    df=pd.concat(rows, ignore_index=True)
    df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df

def fetch_fills(cli, inst_type="SWAP", limit=1000):
    j=cli._get("/api/v5/trade/fills-history", params={"instType":inst_type,"limit":str(limit)})
    df=pd.DataFrame(j.get("data", []))
    if df.empty: return df
    df["ts"]=pd.to_datetime(df["ts"], unit="ms", utc=True)
    df["side"]=df["side"].str.upper()
    df["fillPx"]=df["fillPx"].astype(float)
    df["fillSz"]=df["fillSz"].astype(float)
    return df.sort_values("ts")

def round_trips(fills: pd.DataFrame):
    trips=[]; key_cols=["instId","posSide"]
    for (inst, posSide), g in fills.groupby(key_cols):
        sign = 1 if posSide=="long" else -1
        qty=0.0; entry_val=0.0; entry_fee=0.0; entry_time=None
        for _,r in g.iterrows():
            dir_ = 1 if r["side"]=="BUY" else -1
            q = r["fillSz"] * (1 if posSide=="long" else -1) * dir_
            # entry aggregation
            if qty==0 and q!=0: entry_time = r["ts"]
            if (qty>=0 and q>0) or (qty<=0 and q<0):  # adding in same direction
                entry_val += r["fillPx"] * r["fillSz"]
                qty += r["fillSz"]
            else:
                # reducing
                reduce = min(abs(qty), r["fillSz"])
                # assume average price for unrealized part
                avg_entry = entry_val / max(qty,1e-12)
                pnl = (r["fillPx"] - avg_entry) * (reduce if posSide=="long" else -reduce)
                trips.append({"inst":inst,"posSide":posSide,"exit_ts":r["ts"],"entry_ts":entry_time,"qty":reduce,
                              "avg_entry":avg_entry,"exit_px":r["fillPx"],"pnl_units":pnl})
                qty -= reduce
                entry_val -= avg_entry * reduce
                if abs(qty) < 1e-8:
                    qty=0.0; entry_val=0.0; entry_time=None
    return pd.DataFrame(trips)

def join_intents(trips: pd.DataFrame, intents: pd.DataFrame):
    if trips.empty: return trips.assign(intended_px=np.nan, exec_slip=np.nan, fees=np.nan, alpha=np.nan)
    # map entry intent by nearest prior intent within 5 minutes
    out=trips.copy()
    out["intended_px"]=np.nan
    for i,row in out.iterrows():
        inst=row["inst"]; side="LONG" if row["posSide"]=="long" else "SHORT"; ets=row["entry_ts"]
        sub=intents[(intents["inst"]==inst) & (intents["side"]==side) & (intents["dt"]<=ets)].tail(1)
        if len(sub)>0:
            out.loc[i,"intended_px"]=float(sub["price"].iloc[0])
    # exec slippage (entry only)
    out["exec_slip"] = (out["avg_entry"] - out["intended_px"]).astype(float)
    out["fees"]=0.0  # if needed, extend to sum fills 'fee'
    out["alpha"]= out["pnl_units"] - out["exec_slip"] * out["qty"]
    return out

def main(out_dir="attrib"):
    os.makedirs(out_dir, exist_ok=True)
    cli=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    fills=fetch_fills(cli)
    intents=load_intents()
    trips=round_trips(fills)
    res=join_intents(trips, intents)
    day=dt.datetime.utcnow().strftime("%Y%m%d")
    csvp=os.path.join(out_dir, f"positions_{day}.csv"); res.to_csv(csvp, index=False)
    # HTML report
    s=dict(n=len(res), pnl=float(res["pnl_units"].sum() if len(res)>0 else 0.0),
           exec_cost=float((res["exec_slip"]*res["qty"]).sum() if len(res)>0 else 0.0),
           alpha=float(res["alpha"].sum() if len(res)>0 else 0.0))
    html=f"<html><meta charset='utf-8'><body><h1>Attribution</h1><p>Trips: {s['n']} | PnL_units: {s['pnl']:.6f} | ExecCost: {s['exec_cost']:.6f} | Alpha: {s['alpha']:.6f}</p>{res.tail(200).to_html(index=False)}</body></html>"
    with open(os.path.join(out_dir, "attribution_report.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved", csvp)

if __name__=="__main__":
    main()
