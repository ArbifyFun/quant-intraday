import os, yaml
from datetime import datetime, date, time as dtime, timedelta
from zoneinfo import ZoneInfo

DEFAULT_CAL_PATH = os.getenv("QI_CALENDAR_FILE", "calendar.yaml")

class TradeCalendar:
    """
    YAML format:
    timezone: "Asia/Tokyo"
    silent_days: ["2025-01-01","2025-12-31"]  # YYYY-MM-DD
    windows:    # local times
      - "09:30-11:30"
      - "13:00-15:00"
    extra_windows:   # specific UTC datetimes (iso), overrides (open)
      - { start: "2025-09-18T12:00:00Z", end: "2025-09-18T17:00:00Z", label: "FOMC" }
    """
    def __init__(self, path: str | None = None):
        self.path = path or DEFAULT_CAL_PATH
        self.tz = ZoneInfo("UTC")
        self.silent_days = set()
        self.windows_local = None
        self.extra = []
        self.reload()

    def reload(self):
        if not os.path.exists(self.path):
            return
        cfg = yaml.safe_load(open(self.path, "r", encoding="utf-8")) or {}
        tzname = cfg.get("timezone", "UTC")
        try:
            self.tz = ZoneInfo(tzname)
        except Exception:
            self.tz = ZoneInfo("UTC")
        self.silent_days = set((cfg.get("silent_days") or []))
        self.windows_local = self._parse_local_windows(cfg.get("windows"))
        self.extra = cfg.get("extra_windows", []) or []

    def _parse_local_windows(self, arr):
        if not arr: return None
        out=[]
        for s in arr:
            a,b=s.split("-"); h1,m1=a.split(":"); h2,m2=b.split(":")
            out.append((int(h1)*60+int(m1), int(h2)*60+int(m2)))
        return out

    def is_open_now(self, now_utc: datetime | None = None):
        now = now_utc or datetime.now(ZoneInfo("UTC"))
        # extra windows (UTC) override
        for w in self.extra:
            try:
                from dateutil import parser as _p
                s=_p.isoparse(w["start"]); e=_p.isoparse(w["end"])
            except Exception:
                continue
            if s <= now <= e: return True, w.get("label","extra")
        # silent days (local)
        loc = now.astimezone(self.tz)
        d = loc.date().isoformat()
        if d in self.silent_days:
            return False, "silent_day"
        if self.windows_local is None:
            return True, "all"
        m = loc.hour*60+loc.minute
        for s,e in self.windows_local:
            if s <= m <= e:
                return True, "window"
        return False, "closed"
