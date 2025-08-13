from typing import List, Tuple, Optional

def parse_time_windows(s: str) -> Optional[List[Tuple[int,int]]]:
    if not s or s.upper()=="ALL": return None
    out=[]
    for part in s.split(","):
        a,b=part.strip().split("-")
        h1,m1=a.split(":"); h2,m2=b.split(":")
        out.append((int(h1)*60+int(m1), int(h2)*60+int(m2)))
    return out

def is_allowed_time(minutes: int, windows: Optional[List[Tuple[int,int]]]):
    if windows is None: return True
    return any(s<=minutes<=e for s,e in windows)
