import os, yaml
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ValidationError

class InstrumentCfg(BaseModel):
    inst: str
    tf: str = Field(default="5m", pattern=r"^\d+[mh]$")
    risk_share: float = Field(default=1.0, ge=0.0, le=5.0)

class PortfolioCfg(BaseModel):
    instruments: List[InstrumentCfg] = []

class ExecCfg(BaseModel):
    mode: str = Field(default="autoexec", pattern=r"^(simple|slicer|optimizer|pov|lob|autoexec)$")
    prate: float = Field(default=0.12, ge=0.01, le=0.8)
    slice_timeout: int = Field(default=3, ge=1, le=30)

class RiskCfg(BaseModel):
    risk_pct: float = Field(default=0.007, ge=0.0001, le=0.05)
    dd_limit: float = Field(default=0.08, ge=0.01, le=0.5)
    vol_target_daily: float = Field(default=0.02, ge=0.001, le=0.2)
    time_windows: Optional[str] = None

class ExchangeCfg(BaseModel):
    name: str = Field(default="okx", pattern=r"^okx$")
    simulated: bool = False
    account: str = "trade"

class PathsCfg(BaseModel):
    calendar: str = "calendar.yaml"
    portfolio: str = "portfolio.yaml"
    live_dir: str = "live_output"

class QIConfig(BaseModel):
    exchange: ExchangeCfg = ExchangeCfg()
    risk: RiskCfg = RiskCfg()
    execution: ExecCfg = ExecCfg()
    portfolio: PortfolioCfg = PortfolioCfg()
    paths: PathsCfg = PathsCfg()

def load_qi_config(path: str = "qi.yaml") -> QIConfig:
    if not os.path.exists(path):
        return QIConfig()
    raw = yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    try:
        return QIConfig(**raw)
    except ValidationError as e:
        # Re-raise with useful message
        raise RuntimeError("Invalid qi.yaml: " + e.json())
