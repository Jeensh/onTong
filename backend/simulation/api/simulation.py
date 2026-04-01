"""Section 3 Simulation API — scenario execution and job management.

Endpoints:
    GET  /api/simulation/health           → Section 3 health check
    GET  /api/simulation/scenarios        → Available scenario types
    POST /api/simulation/scenario         → Submit scenario for execution
    GET  /api/simulation/job/{job_id}     → Poll job status
    DELETE /api/simulation/job/{job_id}   → Cancel job
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from backend.shared.contracts.simulation import (
    ScenarioInfo,
    SimulationJob,
    SimulationRequest,
)
from backend.simulation.client.modeling_client import ModelingClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

_client: ModelingClient | None = None


def init(client: ModelingClient) -> None:
    """Inject the modeling client (mock or real)."""
    global _client
    _client = client
    logger.info("Simulation API initialized")


def _get_client() -> ModelingClient:
    if _client is None:
        raise RuntimeError("Simulation API not initialized — call init() first")
    return _client


@router.get("/health")
async def health():
    """Section 3 health check."""
    return {
        "section": "simulation",
        "status": "healthy",
        "mock_mode": type(_client).__name__ == "MockModelingClient" if _client else None,
    }


@router.get("/scenarios", response_model=list[ScenarioInfo])
async def list_scenarios():
    """List available simulation scenario types."""
    client = _get_client()
    return await client.list_scenarios()


@router.post("/scenario", response_model=SimulationJob)
async def submit_scenario(request: SimulationRequest):
    """Submit a simulation scenario for execution. Returns a job."""
    client = _get_client()
    try:
        job = await client.submit_scenario(request)
        logger.info(f"Simulation job submitted: {job.job_id} ({request.scenario_type})")
        return job
    except Exception as e:
        logger.error(f"Simulation submit failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/job/{job_id}", response_model=SimulationJob)
async def get_job(job_id: str):
    """Poll job status and result."""
    client = _get_client()
    job = await client.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return job


@router.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a running simulation job."""
    client = _get_client()
    cancelled = await client.cancel_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (not running)")
    return {"job_id": job_id, "status": "cancelled"}
