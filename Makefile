run:
\tpython scripts/run_live.py --inst BTC-USDT-SWAP --tf 5m --strategy auto --live true --exec-mode autoexec
pref:
\tpython scripts/preflight.py
multi:
\tpython scripts/run_multi_live.py --cfg portfolio.yaml --risk 0.007 --dd 0.08
attr:
\tpython scripts/attr_pnl_v2.py
auto:
\tpython scripts/autopilot_plus.py && python scripts/kelly_scaler.py && python scripts/rebalance.py
