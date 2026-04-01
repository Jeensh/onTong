"""Section 2 ↔ 3 typed simulation contracts.

This module defines the complete API contract between:
- Section 2 (Modeling): executes simulations, returns typed results
- Section 3 (Simulation): designs scenarios, visualizes results

Rules:
- NO `dict` parameters — every scenario has a typed Pydantic model
- NO synchronous execution — all simulations return a Job (async)
- Output types are explicit — ChartOutput, TableOutput, GanttOutput
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


# ── Output Formats ───────────────────────────────────────────────────

class OutputFormat(str, Enum):
    TABLE = "table"
    CHART_LINE = "chart_line"
    CHART_BAR = "chart_bar"
    GANTT = "gantt"
    GRAPH = "graph"
    RAW_JSON = "raw_json"


# ── Scenario Parameters (typed per scenario) ─────────────────────────

class DemandForecastParams(BaseModel):
    scenario_type: Literal["demand_forecast"] = "demand_forecast"
    product_id: str
    forecast_horizon_days: int = 90
    confidence_level: float = 0.95
    include_seasonality: bool = True


class InventoryOptimizeParams(BaseModel):
    scenario_type: Literal["inventory_optimize"] = "inventory_optimize"
    warehouse_id: str
    target_service_level: float = 0.98
    safety_stock_method: Literal["fixed", "dynamic", "demand_driven"] = "dynamic"
    holding_cost_per_unit: float = 1.0


class LeadTimeAnalysisParams(BaseModel):
    scenario_type: Literal["lead_time_analysis"] = "lead_time_analysis"
    supplier_id: str
    delay_days: int = 0
    affected_materials: list[str] = []


# Discriminated union — Section 3 sends one of these, Section 2 validates
ScenarioParams = Annotated[
    DemandForecastParams | InventoryOptimizeParams | LeadTimeAnalysisParams,
    Field(discriminator="scenario_type"),
]


# ── Output Types ─────────────────────────────────────────────────────

class ChartSeries(BaseModel):
    name: str
    data: list[float]


class ChartOutput(BaseModel):
    chart_type: Literal["line", "bar", "scatter"]
    x_label: str
    y_label: str
    x_data: list[str | float]
    series: list[ChartSeries]


class ColumnDef(BaseModel):
    key: str
    label: str
    type: Literal["string", "number", "date", "percent"]


class TableOutput(BaseModel):
    columns: list[ColumnDef]
    rows: list[dict]


class GanttTask(BaseModel):
    id: str
    name: str
    start: datetime
    end: datetime
    progress: float = 0.0
    dependencies: list[str] = []


class GanttOutput(BaseModel):
    tasks: list[GanttTask]


# ── Simulation Job Lifecycle ─────────────────────────────────────────

class SimulationJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SimulationError(BaseModel):
    code: str              # "AMBIGUOUS_PARAMETER", "SANDBOX_LIMIT", etc.
    message: str
    details: dict | None = None
    retryable: bool = False


class SimulationRequest(BaseModel):
    scenario_type: str
    parameters: ScenarioParams
    output_formats: list[OutputFormat] = [OutputFormat.TABLE]
    timeout_sec: int = 120


class SimulationResult(BaseModel):
    outputs: dict[str, ChartOutput | TableOutput | GanttOutput]
    execution_time_ms: int
    uncertainty_range: dict | None = None
    metadata: dict = {}


class SimulationJob(BaseModel):
    job_id: str
    status: SimulationJobStatus
    created_at: datetime
    estimated_duration_sec: int | None = None
    progress_pct: float | None = None
    result: SimulationResult | None = None
    error: SimulationError | None = None


# ── Scenario Registry ────────────────────────────────────────────────

class ScenarioInfo(BaseModel):
    """Metadata about an available simulation scenario type."""
    scenario_type: str
    name: str                  # human-readable Korean name
    description: str
    parameter_schema: dict     # JSON Schema for the parameter model
    supported_outputs: list[OutputFormat]
