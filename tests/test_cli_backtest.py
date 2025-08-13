from typer.testing import CliRunner
from quant_intraday import cli


def test_cli_backtest_runs(tmp_path):
    p = tmp_path / "data.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        f.write("dt,open,high,low,close\n")
        f.write("2024-01-01T00:00:00Z,1,2,0.5,1.5\n")
        f.write("2024-01-01T00:05:00Z,1.5,2.5,1.0,2.0\n")
        f.write("2024-01-01T00:10:00Z,2.0,3.0,1.5,2.5\n")
    runner = CliRunner()
    result = runner.invoke(cli.app, ["backtest", str(p), "--strategy", "trend", "--inst", "BTC-USDT-SWAP"])
    assert result.exit_code == 0
    assert "equity_final" in result.stdout
