from quant_intraday.utils.calendar import TradeCalendar
def test_calendar_open():
    cal=TradeCalendar(path='calendar.yaml')
    open_now,_=cal.is_open_now()
    assert isinstance(open_now, bool)
