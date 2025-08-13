#!/usr/bin/env python3
"""
Attribution v2: entry+exit execution costs and alpha split. Buckets by instrument/strategy.
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

def fetch_fills(cli, inst_type="SWAP", limit=2000):
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
        qty=0.0; entry_val=0.0; entry_time=None; entry_side="BUY" if posSide=="long" else "SELL"
        for _,r in g.iterrows():
            dir_ = 1 if r["side"]=="BUY" else -1
            sz = r["fillSz"]
            if (posSide=="long" and dir_>0) or (posSide=="short" and dir_<0):
                # entry leg
                if qty==0: entry_time=r["ts"]
                qty += sz
                entry_val += r["fillPx"]*sz
            else:
                # exit leg
                if qty<=0: 
                    continue
                reduce = min(qty, sz)
                avg_entry = entry_val / max(qty,1e-12)
                pnl_units = (r["fillPx"] - avg_entry) * (reduce if posSide=="long" else -reduce)
                trips.append({"inst":inst,"posSide":posSide,"entry_ts":entry_time,"exit_ts":r["ts"],"qty":reduce,
                              "avg_entry":avg_entry,"exit_px":r["fillPx"],"side_entry":entry_side})
                qty -= reduce
                entry_val -= avg_entry * reduce
                if qty<=1e-9: qty=0.0; entry_val=0.0; entry_time=None
    return pd.DataFrame(trips)

def infer_intended_exit(row, intent_row):
    if intent_row is None: return np.nan
    tp=float(intent_row["tp"]); sl=float(intent_row["sl"]); side=intent_row["side"]
    if side=="LONG":
        # if exit price is closer to tp or >= tp -> tp; if <= sl -> sl; else unknown -> nearest
        if row["exit_px"] >= tp*0.999: return tp
        if row["exit_px"] <= sl*1.001: return sl
        return tp if abs(row["exit_px"]-tp) < abs(row["exit_px"]-sl) else sl
    else:
        if row["exit_px"] <= tp*1.001: return tp
        if row["exit_px"] >= sl*0.999: return sl
        return tp if abs(row["exit_px"]-tp) < abs(row["exit_px"]-sl) else sl

def sign_from_pos(posSide): return 1 if posSide=="long" else -1

def join_intents(trips: pd.DataFrame, intents: pd.DataFrame):
    out=trips.copy()
    out["strategy"]="unknown"; out["intended_entry"]=np.nan; out["intended_exit"]=np.nan
    for i,row in out.iterrows():
        inst=row["inst"]; ets=row["entry_ts"]; side="LONG" if row["posSide"]=="long" else "SHORT"
        sub=intents[(intents["inst"]==inst) & (intents["side"]==side) & (intents["dt"]<=ets)].tail(1)
        if len(sub)>0:
            out.at[i,"intended_entry"]=float(sub["price"].iloc[0])
            out.at[i,"strategy"]=str(sub["reason"].iloc[0]).split("|")[0].strip()
            out.at[i,"intended_exit"]=infer_intended_exit(row, sub.iloc[0])
    # costs
    sgn = out["posSide"].map(lambda x: 1 if x=="long" else -1).astype(int)
    out["exec_cost_entry"] = (out["avg_entry"] - out["intended_entry"]) * sgn * out["qty"]
    out["exec_cost_exit"]  = (out["intended_exit"] - out["exit_px"]) * sgn * out["qty"]
    out["pnl_units"] = (out["exit_px"] - out["avg_entry"]) * out["qty"] * sgn
    out["alpha"] = out["pnl_units"] - out["exec_cost_entry"].fillna(0.0) - out["exec_cost_exit"].fillna(0.0)
    return out

def buckets(df):
    agg_cols=["pnl_units","exec_cost_entry","exec_cost_exit","alpha"]
    by_inst = df.groupby("inst")[agg_cols].sum().reset_index()
    by_strat = df.groupby("strategy")[agg_cols].sum().reset_index()
    return by_inst, by_strat

def main(out_dir="attrib"):
    os.makedirs(out_dir, exist_ok=True)
    cli=OKXClient(os.getenv("OKX_API_KEY"), os.getenv("OKX_API_SECRET"), os.getenv("OKX_API_PASSPHRASE"), os.getenv("OKX_ACCOUNT","trade"))
    fills=fetch_fills(cli); intents=load_intents()
    trips=round_trips(fills)
    res=join_intents(trips, intents)
    by_inst, by_strat = buckets(res) if not res.empty else (res,res)
    day=dt.datetime.utcnow().strftime("%Y%m%d")
    res.to_csv(os.path.join(out_dir, f"positions_{day}.csv"), index=False)
    html="<html><meta charset='utf-8'><body><h1>Attribution v2</h1>"
    def tbl(df, title):
        return f"<h2>{title}</h2>"+(df.to_html(index=False) if not df.empty else "<p>无数据</p>")
    html += tbl(res.tail(200), "明细（近期200条）")
    html += tbl(by_inst, "按品种汇总")
    html += tbl(by_strat, "按策略汇总")
    html += "</body></html>"
    with open(os.path.join(out_dir, "attribution_report.html"), "w", encoding="utf-8") as f: f.write(html)
    print("Saved attribution to", out_dir)

if __name__=="__main__":
    main()
