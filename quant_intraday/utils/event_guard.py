import os, yaml
from datetime import datetime, timezone

DEFAULT_PATH = os.getenv("QI_EVENTS_FILE","events_blackout.yaml")

class EventGuard:
    def __init__(self, path:str=None):
        self.path=path or DEFAULT_PATH
        self._cfg={"windows":[]}; self.reload()
    def reload(self):
        if os.path.exists(self.path):
            with open(self.path,"r",encoding="utf-8") as f:
                self._cfg = yaml.safe_load(f) or {"windows":[]}
        else:
            self._cfg={"windows":[]}
    def is_blocked(self, inst_id: str, now_utc: datetime=None):
        now = now_utc or datetime.now(timezone.utc)
        for w in self._cfg.get("windows", []):
            try:
                s=datetime.fromisoformat(w["start"].replace("Z","+00:00"))
                e=datetime.fromisoformat(w["end"].replace("Z","+00:00"))
            except Exception:
                continue
            appl=w.get("apply",["ALL"])
            if s<=now<=e and ("ALL" in appl or inst_id in appl):
                return True, w.get("label","")
        return False, ""
