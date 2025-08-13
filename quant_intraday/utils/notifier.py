import os, json, httpx, logging

WEBHOOK=os.getenv("QI_WEBHOOK_URL", None)

logger=logging.getLogger(__name__)

async def notify(event: str, payload: dict | None = None) -> bool:
    if not WEBHOOK:
        return False
    try:
        body={"event": event, "payload": payload or {}}
        async with httpx.AsyncClient() as client:
            await client.post(WEBHOOK, json=body, timeout=5)
        return True
    except httpx.HTTPError as e:
        logger.warning("notify failed: %s", e)
        return False
