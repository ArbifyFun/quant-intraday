from quant_intraday.utils.time_windows import parse_time_windows

def test_parse():
    w=parse_time_windows('09:30-11:30,13:00-15:00')
    assert w[0]==(570,690)
