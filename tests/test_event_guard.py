from quant_intraday.utils.event_guard import EventGuard
from datetime import datetime, timezone

def test_event():
    eg=EventGuard(path='events_blackout.yaml')
    b,l=eg.is_blocked('BTC-USDT-SWAP', datetime(2025,8,13,13,0,0,tzinfo=timezone.utc))
    assert b
