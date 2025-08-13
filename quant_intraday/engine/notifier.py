import os
import httpx

class Notifier:
    """Simple notifier for sending messages to Telegram and Feishu."""

    def send_tg(self, text: str) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat:
            return
        try:
            httpx.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat, "text": text},
                timeout=5.0,
            )
        except Exception:
            pass

    def send_feishu(self, text: str) -> None:
        url = os.getenv("FEISHU_WEBHOOK_URL")
        if not url:
            return
        try:
            httpx.post(
                url,
                json={"msg_type": "text", "content": {"text": text}},
                timeout=5.0,
            )
        except Exception:
            pass

    def notify(self, text: str) -> None:
        """Broadcast message to all configured channels."""
        self.send_tg(text)
        self.send_feishu(text)
