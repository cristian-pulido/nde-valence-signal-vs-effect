from pathlib import Path

from nde_analysis.config import load_config


def test_config_loads_default():
    cfg = load_config(config_path=Path("configs/default.yaml"))
    assert str(cfg.data_path).endswith("../../DATA/data_for_model.csv")
    assert cfg.plot.format == "png"
