#!/usr/bin/env python3
import os, io, base64, httpx, pandas as pd, matplotlib.pyplot as plt
def make_chart(eq_csv="live_output/equity.csv"):
    df=pd.read_csv(eq_csv, names=["ts","equity"], header=0); df["dt"]=pd.to_datetime(df["ts"], unit="ms", utc=True); s=df.set_index("dt")["equity"]
    fig=plt.figure(); plt.plot(s.index, s.values); plt.title("Live Equity"); plt.xlabel("time"); plt.ylabel("equity")
    buf=io.BytesIO(); fig.savefig(buf, format="png", dpi=140, bbox_inches="tight"); plt.close(fig); return buf.getvalue()
def send_telegram_photo(img_bytes, caption="Equity"):
    tok=os.getenv("TELEGRAM_BOT_TOKEN"); chat=os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat: print("telegram env missing"); return
    files={"photo": ("equity.png", img_bytes, "image/png")}; data={"chat_id": chat, "caption": caption}
    httpx.post(f"https://api.telegram.org/bot{tok}/sendPhoto", data=data, files=files, timeout=10.0)
if __name__=="__main__": img=make_chart(); send_telegram_photo(img, "Live Equity")
