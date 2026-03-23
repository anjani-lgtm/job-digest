"""Abstract base class for job sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from job_digest.models import Job


class JobSource(ABC):
    """Base class all job sources must implement."""

    name: str = "base"

    @abstractmethod
    async def fetch(self) -> list[Job]:
        """Fetch jobs from this source. Returns normalized Job objects."""
        ...
