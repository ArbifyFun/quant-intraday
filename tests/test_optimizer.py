from quant_intraday.engine.optimizer import ExecOptimizer
def test_opt_config():
    e=ExecOptimizer(step_ticks=2, slice_timeout_s=4, max_reposts=3, cross_when_last=False)
    assert e.step_ticks==2 and e.max_reposts==3
