"""Base agent interface and utilities."""

import time
from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel

from app.core.logging import get_logger
from app.models.trace import AgentTrace
from app.schemas.trace_schema import TraceCreate

logger = get_logger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all agents.

    Agents are stateless and receive/return Pydantic models.
    All state is persisted to the database after each step.
    """

    name: str = "BaseAgent"

    @abstractmethod
    def execute(self, input_data: InputT) -> OutputT:
        """Execute the agent's primary function.

        Args:
            input_data: Pydantic model with input parameters.

        Returns:
            Pydantic model with output results.
        """
        pass

    def create_trace(
        self,
        run_id: UUID,
        action: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        duration_ms: float | None = None,
    ) -> TraceCreate:
        """Create a trace entry for this agent's action.

        Args:
            run_id: UUID of the discovery run.
            action: Description of the action performed.
            input_data: Input parameters (serialized).
            output_data: Output results (serialized).
            duration_ms: Duration of the operation.

        Returns:
            TraceCreate schema ready for database insertion.
        """
        return TraceCreate(
            run_id=run_id,
            agent_name=self.name,
            action=action,
            input_data=input_data,
            output_data=output_data,
            duration_ms=duration_ms,
        )

    def log_action(
        self,
        action: str,
        **kwargs: Any,
    ) -> None:
        """Log an agent action with structured logging.

        Args:
            action: Description of the action.
            **kwargs: Additional context to log.
        """
        logger.info(
            "agent_action",
            agent=self.name,
            action=action,
            **kwargs,
        )


class TimedExecution:
    """Context manager for timing agent operations."""

    def __init__(self) -> None:
        self.start_time: float = 0
        self.duration_ms: float = 0

    def __enter__(self) -> "TimedExecution":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        end_time = time.perf_counter()
        self.duration_ms = (end_time - self.start_time) * 1000
