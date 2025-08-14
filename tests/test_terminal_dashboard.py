import csv
from datetime import datetime, timezone
from quant_intraday.scripts import terminal_dashboard as td


def test_read_equity(tmp_path):
    p = tmp_path / "equity.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "equity"])
        w.writeheader()
        w.writerow({"ts": "0", "equity": "100"})
        w.writerow({"ts": "1", "equity": "90"})
    eq = td._read_equity(str(p))
    assert eq is not None
    assert abs(eq[0] - 90.0) < 1e-6
    assert abs(eq[1] - (-0.1)) < 1e-6


def test_read_trades_limit_and_time(tmp_path):
    p = tmp_path / "trades.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ts", "inst", "side", "price", "qty"])
        w.writeheader()
        w.writerow({"ts": 1000, "inst": "foo", "side": "buy", "price": "1", "qty": "2"})
        w.writerow({"ts": 2000, "inst": "bar", "side": "sell", "price": "3", "qty": "4"})
        w.writerow({"ts": 3000, "inst": "baz", "side": "buy", "price": "5", "qty": "6"})
    rows = td._read_trades(str(p), limit=2)
    assert [r["inst"] for r in rows] == ["bar", "baz"]
    expect = datetime.fromtimestamp(2000 / 1000, tz=timezone.utc).strftime("%H:%M:%S")
    assert rows[0]["time"] == expect


def test_read_json_helpers(tmp_path):
    import json

    kpi_p = tmp_path / "exec_kpis.json"
    pos_p = tmp_path / "positions.json"
    sig_p = tmp_path / "signals.json"
    with open(kpi_p, "w", encoding="utf-8") as f:
        json.dump({"by_inst": {"BTC-USDT": {"fill_rate": 1.0}}}, f)
    with open(pos_p, "w", encoding="utf-8") as f:
        json.dump({"positions": [{"inst": "BTC-USDT", "qty": 1, "pnl": 0.5}]}, f)
    with open(sig_p, "w", encoding="utf-8") as f:
        json.dump({"signals": [{"inst": "BTC-USDT", "signal": "buy", "score": 0.8}]}, f)

    assert td._read_kpis(str(kpi_p)) == {"BTC-USDT": {"fill_rate": 1.0}}
    assert td._read_positions(str(pos_p)) == [{"inst": "BTC-USDT", "qty": 1, "pnl": 0.5}]
    assert td._read_signals(str(sig_p)) == [{"inst": "BTC-USDT", "signal": "buy", "score": 0.8}]

    # missing files should fall back to defaults
    assert td._read_kpis(str(tmp_path / "missing.json")) == {}
    assert td._read_positions(str(tmp_path / "missing2.json")) == []
    assert td._read_signals(str(tmp_path / "missing3.json")) == []


def test_refresh_updates_layout(tmp_path):
    (tmp_path / "equity.csv").write_text("ts,equity\n0,1\n", encoding="utf-8")
    (tmp_path / "exec_kpis.json").write_text("{""by_inst"": {""BTC"": {""fill_rate"": 0.9}}}", encoding="utf-8")
    (tmp_path / "positions.json").write_text("{""positions"": [{""inst"": ""BTC"", ""qty"": 1, ""pnl"": 1}]}", encoding="utf-8")
    (tmp_path / "signals.json").write_text("{""signals"": [{""inst"": ""BTC"", ""signal"": ""buy"", ""score"": 1}]}", encoding="utf-8")
    (tmp_path / "trades.csv").write_text("ts,inst,side,price,qty\n0,BTC,buy,1,1\n", encoding="utf-8")

    layout = td._init_layout()
    td._refresh(layout, str(tmp_path), 5)

    for name, title in [
        ("header", "权益"),
        ("kpi", "执行 KPI"),
        ("positions", "仓位"),
        ("signals", "信号"),
        ("trades", "最近成交"),
    ]:
        panel = layout[name].renderable
        assert getattr(panel, "title", None) == title

    assert "UTC" in layout["kpi"].renderable.subtitle
