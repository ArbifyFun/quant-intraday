import importlib
import sys
import builtins
import numpy as np

from quant_intraday.utils import talib_fallback


def test_talib_wrapper_fallback(monkeypatch):
    """Wrapper should fall back to pure-Python implementations when TALib is missing."""
    monkeypatch.delitem(sys.modules, "talib", raising=False)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "talib":
            raise ImportError
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    module_name = "quant_intraday.utils.talib_wrapper"
    if module_name in sys.modules:
        del sys.modules[module_name]
    wrapper = importlib.import_module(module_name)

    c = np.array([1.0, 2.0, 3.0])
    h = l = c
    res = wrapper.ta.ATR(h, l, c, 1)
    exp = talib_fallback.ATR(h, l, c, 1)
    assert np.allclose(res, exp)
