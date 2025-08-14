import logging
from quant_intraday.scripts import exec_kpi_daemon as ekd


def test_compute_logs_read_error(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(ekd, "LIVE", str(tmp_path))
    # Ensure execlog.csv exists but pd.read_csv fails
    (tmp_path / "execlog.csv").write_text("bad", encoding="utf-8")
    def bad_read_csv(*_args, **_kwargs):
        raise ValueError("boom")
    monkeypatch.setattr(ekd.pd, "read_csv", bad_read_csv)
    assert ekd.compute() == {}
    assert "failed to read execlog.csv" in caplog.text


def test_main_logs_and_continues(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    calls = []

    def fake_compute():
        calls.append(1)
        raise RuntimeError("boom")

    def fake_sleep(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(ekd, "compute", fake_compute)
    monkeypatch.setattr(ekd.time, "sleep", fake_sleep)
    try:
        ekd.main()
    except KeyboardInterrupt:
        pass
    assert calls == [1]
    assert "exec_kpi_daemon loop error" in caplog.text
