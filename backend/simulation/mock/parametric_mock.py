"""Parametric mock server for Section 2 simulation API.

NOT static JSON — generates dynamic responses based on input parameters.
Used during independent development before Section 2 is ready.

Usage:
    client = MockModelingClient()
    job = await client.submit_scenario(request)
    # job.status == PENDING initially
    job = await client.get_job(job.job_id)
    # job.status == COMPLETED with generated result
"""

from __future__ import annotations

import hashlib
import math
import random
import uuid
from datetime import datetime, timedelta

from backend.shared.contracts.simulation import (
    ChartOutput,
    ChartSeries,
    ColumnDef,
    DemandForecastParams,
    GanttOutput,
    GanttTask,
    InventoryOptimizeParams,
    LeadTimeAnalysisParams,
    OutputFormat,
    ScenarioInfo,
    SimulationJob,
    SimulationJobStatus,
    SimulationRequest,
    SimulationResult,
    TableOutput,
)


class MockModelingClient:
    """Parametric mock that generates plausible simulation results."""

    def __init__(self) -> None:
        self._jobs: dict[str, SimulationJob] = {}

    async def submit_scenario(self, request: SimulationRequest) -> SimulationJob:
        job_id = str(uuid.uuid4())
        # Generate result immediately (mock doesn't need async processing)
        result = _generate_result(request)
        job = SimulationJob(
            job_id=job_id,
            status=SimulationJobStatus.COMPLETED,
            created_at=datetime.now(),
            estimated_duration_sec=2,
            progress_pct=100.0,
            result=result,
        )
        self._jobs[job_id] = job
        return job

    async def get_job(self, job_id: str) -> SimulationJob | None:
        return self._jobs.get(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.status in (SimulationJobStatus.PENDING, SimulationJobStatus.RUNNING):
            job.status = SimulationJobStatus.CANCELLED
            return True
        return False

    async def list_scenarios(self) -> list[ScenarioInfo]:
        return [
            ScenarioInfo(
                scenario_type="demand_forecast",
                name="수요 예측",
                description="제품별 수요를 예측하고 계절성을 분석합니다.",
                parameter_schema=DemandForecastParams.model_json_schema(),
                supported_outputs=[OutputFormat.CHART_LINE, OutputFormat.TABLE],
            ),
            ScenarioInfo(
                scenario_type="inventory_optimize",
                name="재고 최적화",
                description="창고별 안전 재고 수준을 최적화합니다.",
                parameter_schema=InventoryOptimizeParams.model_json_schema(),
                supported_outputs=[OutputFormat.TABLE, OutputFormat.CHART_BAR],
            ),
            ScenarioInfo(
                scenario_type="lead_time_analysis",
                name="리드타임 영향 분석",
                description="공급업체 납기 지연이 생산 계획에 미치는 영향을 분석합니다.",
                parameter_schema=LeadTimeAnalysisParams.model_json_schema(),
                supported_outputs=[OutputFormat.GANTT, OutputFormat.TABLE],
            ),
        ]


# ── Result generators (parametric, NOT static) ──────────────────────


def _seed_from_params(params) -> int:
    """Deterministic seed from parameter values — same input = same output."""
    h = hashlib.md5(str(params.model_dump()).encode()).hexdigest()
    return int(h[:8], 16)


def _generate_result(request: SimulationRequest) -> SimulationResult:
    params = request.parameters
    rng = random.Random(_seed_from_params(params))
    outputs: dict[str, ChartOutput | TableOutput | GanttOutput] = {}

    if isinstance(params, DemandForecastParams):
        outputs = _demand_forecast(params, request.output_formats, rng)
    elif isinstance(params, InventoryOptimizeParams):
        outputs = _inventory_optimize(params, request.output_formats, rng)
    elif isinstance(params, LeadTimeAnalysisParams):
        outputs = _lead_time_analysis(params, request.output_formats, rng)

    return SimulationResult(
        outputs=outputs,
        execution_time_ms=rng.randint(200, 2000),
        metadata={"mock": True, "scenario_type": request.scenario_type},
    )


def _demand_forecast(
    params: DemandForecastParams,
    formats: list[OutputFormat],
    rng: random.Random,
) -> dict:
    days = params.forecast_horizon_days
    base = rng.uniform(100, 500)
    trend = rng.uniform(-0.5, 2.0)
    outputs = {}

    x_data = [(datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
    forecast = []
    upper = []
    lower = []
    for i in range(days):
        seasonal = math.sin(2 * math.pi * i / 30) * 20 if params.include_seasonality else 0
        val = base + trend * i + seasonal + rng.gauss(0, 10)
        forecast.append(round(val, 1))
        margin = val * (1 - params.confidence_level) * 3
        upper.append(round(val + margin, 1))
        lower.append(round(val - margin, 1))

    if OutputFormat.CHART_LINE in formats:
        outputs[OutputFormat.CHART_LINE.value] = ChartOutput(
            chart_type="line",
            x_label="날짜",
            y_label="수요량",
            x_data=x_data,
            series=[
                ChartSeries(name="예측", data=forecast),
                ChartSeries(name="상한", data=upper),
                ChartSeries(name="하한", data=lower),
            ],
        )

    if OutputFormat.TABLE in formats:
        outputs[OutputFormat.TABLE.value] = TableOutput(
            columns=[
                ColumnDef(key="date", label="날짜", type="date"),
                ColumnDef(key="forecast", label="예측 수요", type="number"),
                ColumnDef(key="upper", label="상한", type="number"),
                ColumnDef(key="lower", label="하한", type="number"),
            ],
            rows=[
                {"date": x_data[i], "forecast": forecast[i], "upper": upper[i], "lower": lower[i]}
                for i in range(min(30, days))  # first 30 rows for table
            ],
        )

    return outputs


def _inventory_optimize(
    params: InventoryOptimizeParams,
    formats: list[OutputFormat],
    rng: random.Random,
) -> dict:
    outputs = {}
    items = [f"MTL-{rng.randint(1000, 9999)}" for _ in range(8)]
    current_stock = [rng.randint(50, 300) for _ in items]
    optimal_stock = [
        round(cs * params.target_service_level * rng.uniform(0.8, 1.2))
        for cs in current_stock
    ]
    savings = [
        round((cs - os) * params.holding_cost_per_unit, 2)
        for cs, os in zip(current_stock, optimal_stock)
    ]

    if OutputFormat.TABLE in formats:
        outputs[OutputFormat.TABLE.value] = TableOutput(
            columns=[
                ColumnDef(key="material", label="자재 코드", type="string"),
                ColumnDef(key="current", label="현재 재고", type="number"),
                ColumnDef(key="optimal", label="최적 재고", type="number"),
                ColumnDef(key="saving", label="절감액", type="number"),
            ],
            rows=[
                {"material": items[i], "current": current_stock[i],
                 "optimal": optimal_stock[i], "saving": savings[i]}
                for i in range(len(items))
            ],
        )

    if OutputFormat.CHART_BAR in formats:
        outputs[OutputFormat.CHART_BAR.value] = ChartOutput(
            chart_type="bar",
            x_label="자재",
            y_label="재고량",
            x_data=items,
            series=[
                ChartSeries(name="현재 재고", data=[float(s) for s in current_stock]),
                ChartSeries(name="최적 재고", data=[float(s) for s in optimal_stock]),
            ],
        )

    return outputs


def _lead_time_analysis(
    params: LeadTimeAnalysisParams,
    formats: list[OutputFormat],
    rng: random.Random,
) -> dict:
    outputs = {}
    now = datetime.now()
    materials = params.affected_materials or [f"MAT-{rng.randint(100, 999)}" for _ in range(5)]

    tasks = []
    for i, mat in enumerate(materials):
        start = now + timedelta(days=i * 3)
        original_end = start + timedelta(days=rng.randint(5, 15))
        delayed_end = original_end + timedelta(days=params.delay_days)
        tasks.append(GanttTask(
            id=f"task-{i}",
            name=f"{mat} 조달",
            start=start,
            end=delayed_end,
            progress=0.0,
            dependencies=[f"task-{i-1}"] if i > 0 else [],
        ))

    if OutputFormat.GANTT in formats:
        outputs[OutputFormat.GANTT.value] = GanttOutput(tasks=tasks)

    if OutputFormat.TABLE in formats:
        outputs[OutputFormat.TABLE.value] = TableOutput(
            columns=[
                ColumnDef(key="material", label="자재", type="string"),
                ColumnDef(key="start", label="시작일", type="date"),
                ColumnDef(key="end", label="종료일", type="date"),
                ColumnDef(key="delay", label="지연일수", type="number"),
            ],
            rows=[
                {"material": materials[i], "start": tasks[i].start.isoformat(),
                 "end": tasks[i].end.isoformat(), "delay": params.delay_days}
                for i in range(len(materials))
            ],
        )

    return outputs
