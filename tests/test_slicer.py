from quant_intraday.engine.slicer import SlicerExec
def test_slicer_basic():
    s=SlicerExec(0.1, max_slices=5, slice_timeout_s=1)
    assert s.max_slices==5 and s.slice_timeout_s==1
