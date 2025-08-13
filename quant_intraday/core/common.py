from dataclasses import dataclass
@dataclass
class Signal:
    side: str
    price: float
    sl: float
    tp: float
    reason: str
