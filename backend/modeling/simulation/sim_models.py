"""Pydantic models for parametric simulation."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SimulationParam(BaseModel):
    """A tunable parameter on a code entity."""
    entity_id: str
    param_name: str
    param_type: str = "float"  # float | int | bool
    default_value: str
    current_value: str = ""    # filled from default if empty
    min_value: str | None = None
    max_value: str | None = None
    step: str | None = None
    unit: str = ""
    description: str = ""
    formula: str | None = None  # display-only

    def model_post_init(self, __context) -> None:
        if not self.current_value:
            self.current_value = self.default_value


class SimulationOutput(BaseModel):
    """One computed metric from a simulation run."""
    metric_name: str
    label: str
    before_value: str
    after_value: str
    change_pct: float
    unit: str = ""


class AffectedProcessRef(BaseModel):
    """Lightweight reference to an affected domain process."""
    domain_id: str
    domain_name: str
    distance: int


class ParametricSimResult(BaseModel):
    """Result of running a parametric simulation."""
    entity_id: str
    entity_name: str
    params_before: dict[str, str]
    params_after: dict[str, str]
    outputs: list[SimulationOutput]
    affected_processes: list[AffectedProcessRef]
    message: str
