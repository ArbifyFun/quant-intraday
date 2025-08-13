#!/usr/bin/env python3
import os, httpx, json
def send_feishu_card(title="Quant Alert", text=""):
    url=os.getenv("FEISHU_WEBHOOK_URL")
    if not url: print("FEISHU_WEBHOOK_URL missing"); return
    card={"msg_type":"interactive","card":{"config":{"wide_screen_mode":True},"elements":[{"tag":"div","text":{"tag":"lark_md","content":text}}],"header":{"template":"turquoise","title":{"tag":"plain_text","content":title}}}}
    try: httpx.post(url, json=card, timeout=8.0)
    except Exception as e: print("feishu send error:", e)
if __name__=="__main__": send_feishu_card("Quant Alert","**Test** message from toolkit v7")
