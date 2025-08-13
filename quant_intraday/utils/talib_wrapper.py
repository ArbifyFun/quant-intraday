"""Unified TA-Lib import wrapper.

This module exposes a single object ``ta`` that provides technical
indicator functions.  It first attempts to import the official
``talib`` package.  If that fails (for example when the C extension is
not installed), it falls back to the minimal pure-Python implementations
in :mod:`quant_intraday.utils.talib_fallback`.
"""

from __future__ import annotations

try:  # pragma: no cover - import side effects
    import talib as ta  # type: ignore
except Exception:  # pragma: no cover - no talib available
    from . import talib_fallback as ta  # type: ignore

__all__ = ["ta"]
