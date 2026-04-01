"""Protocol-based client for Section 2 (Modeling) API.

Both MockModelingClient and RealModelingClient implement this Protocol,
so Section 3 code never knows which backend it talks to.

Toggle via SIMULATION_USE_MOCK env var.
"""

from __future__ import annotations

import logging
from typing import Protocol

from backend.shared.contracts.simulation import (
    ScenarioInfo,
    SimulationJob,
    SimulationRequest,
)

logger = logging.getLogger(__name__)


class ModelingClient(Protocol):
    """Interface for calling Section 2 simulation API."""

    async def submit_scenario(self, request: SimulationRequest) -> SimulationJob:
        """Submit a simulation scenario. Returns job with PENDING status."""
        ...

    async def get_job(self, job_id: str) -> SimulationJob | None:
        """Poll job status and result."""
        ...

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        ...

    async def list_scenarios(self) -> list[ScenarioInfo]:
        """List available scenario types with parameter schemas."""
        ...


def create_modeling_client(use_mock: bool = True) -> ModelingClient:
    """Factory — returns mock or real client based on config."""
    if use_mock:
        from backend.simulation.mock.parametric_mock import MockModelingClient
        logger.info("Using MockModelingClient (SIMULATION_USE_MOCK=true)")
        return MockModelingClient()
    else:
        # Phase 2: real HTTP client to Section 2 API
        raise NotImplementedError(
            "Real modeling client not yet implemented. "
            "Set SIMULATION_USE_MOCK=true for now."
        )
