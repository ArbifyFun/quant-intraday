from quant_intraday.engine.pov_executor import POVExecutor
def test_pov_conf():
    e=POVExecutor(0.1, min_child=2, adverse_ticks=3, queue_max=1000, cycle_s=2)
    assert e.min_child==2 and e.adverse_ticks==3
