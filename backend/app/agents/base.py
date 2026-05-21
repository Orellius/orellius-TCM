"""Base agent class with shared utilities."""

import logging
from abc import ABC, abstractmethod

from app.orchestrator.state import PipelineState


class BaseAgent(ABC):
    """Base class for all pipeline agents."""

    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def process(self, state: PipelineState) -> PipelineState:
        """Process the pipeline state and return updated state."""
        ...

    def log_status(self, message_id: str, status: str) -> None:
        self.logger.info(f"[{message_id}] {self.name}: {status}")
