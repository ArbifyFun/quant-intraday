from quant_intraday.core.funding_basis import funding_bias_signal, basis_tilt_signal
def test_fb_signals():
    assert funding_bias_signal({'funding':0.2})==-1
    assert funding_bias_signal({'funding':-0.2})==1
    assert basis_tilt_signal({'basis_bps':50})==1
