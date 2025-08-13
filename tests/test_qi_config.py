import pytest
from quant_intraday.config import load_qi_config


def test_load_qi_config_missing_file(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError) as exc:
        load_qi_config(str(missing))
    assert "Configuration file not found" in str(exc.value)


def test_load_qi_config_invalid_yaml(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("key: [unclosed", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        load_qi_config(str(bad))
    assert "Error parsing YAML configuration" in str(exc.value)
