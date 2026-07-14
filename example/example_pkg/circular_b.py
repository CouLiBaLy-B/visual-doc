"""Module B - Dépendance circulaire avec A."""

from __future__ import annotations

try:
    from . import circular_a  # noqa: F401
except ImportError:
    pass


class ServiceB:
    """Service B qui dépend de A."""

    def __init__(self, name: str = "B"):
        self.name: str = name
        self.a_service: object | None = None

    def set_a(self, a_service) -> None:  # type: ignore[no-untyped-def]
        self.a_service = a_service

    def do_work(self) -> str:
        return f"{self.name} working"

    def call_a(self) -> str:
        if self.a_service:
            return f"B -> A: {self.a_service.do_work()}"  # type: ignore[attr-defined]
        return "B alone"
