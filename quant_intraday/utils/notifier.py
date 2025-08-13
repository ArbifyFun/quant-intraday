import os, json, httpx

WEBHOOK=os.getenv("QI_WEBHOOK_URL", None)

def notify(event: str, payload: dict | None = None):
    if not WEBHOOK: 
        return False
    try:
        body={"event": event, "payload": payload or {}}
        httpx.post(WEBHOOK, json=body, timeout=5)
        return True
    except Exception:
        return False
