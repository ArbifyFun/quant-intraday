import os, csv, threading

_lock = threading.Lock()

def _ensure_header(path, keys):
    exists = os.path.exists(path) and os.path.getsize(path)>0
    if not exists:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(keys))
            w.writeheader()
            return list(keys)
    else:
        # read header
        with open(path, "r", newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            header = next(r, [])
        # if header lacks keys, rewrite header by merging
        union = list(dict.fromkeys([*header, *keys]))
        if union != header:
            # rewrite whole file with new header
            rows = []
            with open(path, "r", newline="", encoding="utf-8") as f:
                r = csv.DictReader(f)
                rows = list(r)
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=union)
                w.writeheader()
                for row in rows:
                    w.writerow(row)
        return union

def write_event(path, data: dict):
    with _lock:
        header = _ensure_header(path, data.keys())
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writerow(data)
