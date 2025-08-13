from quant_intraday.utils.rate_limit import TokenBucket

def test_tb():
    tb=TokenBucket(1,100); assert tb.take(1); assert not tb.take(1)
