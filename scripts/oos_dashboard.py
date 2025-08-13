#!/usr/bin/env python3
import os, io, base64, pandas as pd, matplotlib.pyplot as plt
def _png(s, title):
    fig=plt.figure(); plt.plot(s.index, s.values); plt.title(title); plt.xlabel("time"); plt.ylabel("value")
    import io as _i; b=_i.BytesIO(); fig.savefig(b, format="png", dpi=140, bbox_inches="tight"); plt.close(fig); return base64.b64encode(b.getvalue()).decode()
def main(live_dir="live_output", out_html="oos_dashboard.html"):
    eq_p=os.path.join(live_dir,"equity.csv"); eq=pd.read_csv(eq_p, names=["ts","equity"], header=0); eq["dt"]=pd.to_datetime(eq["ts"], unit="ms", utc=True); s=eq.set_index("dt")["equity"]
    dd=(s/s.cummax()-1.0); eq_png=_png(s,"Live Equity"); dd_png=_png(dd,"Live Drawdown")
    trades_tables=""
    for fn in os.listdir(live_dir):
        if fn.startswith("trades_") and fn.endswith(".csv"):
            df=pd.read_csv(os.path.join(live_dir, fn)); 
            if len(df)>0: df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True); trades_tables+=f"<h3>{fn}</h3>"+df.tail(100).to_html(index=False)
    html=f"<html><head><meta charset='utf-8'/><title>OOS Dashboard</title></head><body><h1>实盘 OOS 看板</h1><h2>权益</h2><img src='data:image/png;base64,{eq_png}'/><h2>回撤</h2><img src='data:image/png;base64,{dd_png}'/><h2>交易（最近100）</h2>{trades_tables}</body></html>"
    with open(out_html,"w",encoding="utf-8") as f: f.write(html); print("Saved", out_html)
if __name__=="__main__": main()
