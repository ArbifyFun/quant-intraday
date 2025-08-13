from quant_intraday.engine.lob_executor import LOBExecutor
def test_lob_conf():
    e=LOBExecutor(widen_ticks=3, narrow_ticks=1, imb_th=0.2, queue_surge=5000, min_dwell_s=2, max_cancels_per_min=30)
    assert e.max_cpm==30 and e.min_dwell_s==2
