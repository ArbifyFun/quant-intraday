#!/usr/bin/env python3
import os, io, base64, pandas as pd, matplotlib.pyplot as plt

HTML_TMPL = """<!DOCTYPE html><html lang='zh'><head><meta charset='utf-8'/><title>Backtest Report</title>
<style>body{font-family:Arial;max-width:1100px;margin:24px auto} .card{border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:16px 0} table{border-collapse:collapse;width:100%} th,td{border-bottom:1px solid #eee;padding:8px 6px;text-align:right} th{text-align:left}</style></head>
<body><h1>回测报告</h1>
<div class='card'><h2>指标摘要</h2><table><tr><th>指标</th><th>数值</th></tr>{rows}</table></div>
<div class='card'><h2>权益曲线</h2><img src="data:image/png;base64,{eq_png}"/></div>
<div class='card'><h2>回撤</h2><img src="data:image/png;base64,{dd_png}"/></div>
<div class='card'><h2>小时胜率</h2><img src="data:image/png;base64,{hr_png}"/></div>
<div class='card'><h2>RR 分布</h2><img src="data:image/png;base64,{rr_png}"/></div>
<div class='card'><h2>交易清单（前 50 条）</h2>{trades_html}</div>
</body></html>"""

def _png_series(s, title):
    fig=plt.figure(); plt.plot(s.index, s.values); plt.title(title); plt.xlabel("time"); plt.ylabel("value")
    buf=io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig); return base64.b64encode(buf.getvalue()).decode()

def main(out_dir="backtest_output", out_html=None):
    eq=pd.read_csv(os.path.join(out_dir,"equity.csv"), index_col=0, parse_dates=True).iloc[:,0]
    dd=(eq/eq.cummax()-1.0)
    eq_png=_png_series(eq,"Equity"); dd_png=_png_series(dd,"Drawdown")
    # trades
    trades_p=os.path.join(out_dir,"trades.csv")
    if os.path.exists(trades_p):
        tdf=pd.read_csv(trades_p, parse_dates=["entry_time","exit_time"])
        hrs=tdf["exit_time"].dt.hour; win=(tdf["pnl"]>0).astype(int); hr=win.groupby(hrs).mean().reindex(range(24)).fillna(0.0)
        fig1=plt.figure(); plt.plot(hr.index, hr.values); plt.title("Hourly Winrate"); plt.xlabel("hour"); plt.ylabel("winrate")
        import io as _io; b1=_io.BytesIO(); fig1.savefig(b1, format="png", dpi=140, bbox_inches="tight"); plt.close(fig1)
        hr_png=base64.b64encode(b1.getvalue()).decode()
        rr=((tdf["exit"]-tdf["entry"]).abs()/(tdf["entry"]-tdf["entry"].shift(1).fillna(tdf["entry"])).abs().replace(0,1)).clip(0,10)
        fig2=plt.figure(); plt.hist(rr.values, bins=30); plt.title("RR Distribution"); plt.xlabel("RR"); plt.ylabel("count")
        b2=_io.BytesIO(); fig2.savefig(b2, format="png", dpi=140, bbox_inches="tight"); plt.close(fig2)
        rr_png=base64.b64encode(b2.getvalue()).decode()
        rows="".join(f"<tr><td>{k}</td><td>{v:.4f}</td></tr>" for k,v in zip(["最终权益","总收益","最大回撤"], [eq.iloc[-1], eq.iloc[-1]/eq.iloc[0]-1.0, float(dd.min())]))
        rows=f"{rows}<tr><td>起始权益</td><td>{eq.iloc[0]:.2f}</td></tr>"
        rows=rows
        rows_html = rows
        trades_html = tdf.head(50).to_html(index=False)
    else:
        hr_png=rr_png=""; rows_html="<tr><td>无数据</td><td>—</td></tr>"; trades_html="<p>没有找到 trades.csv</p>"
    html=HTML_TMPL.format(rows=rows_html, eq_png=eq_png, dd_png=dd_png, hr_png=hr_png, rr_png=rr_png, trades_html=trades_html)
    out_html=out_html or os.path.join(out_dir,"report.html")
    with open(out_html,"w",encoding="utf-8") as f: f.write(html); print("Report saved:", out_html)

if __name__=="__main__": main()
