"""Module A - Dépendance circulaire avec B (pour démo détection)."""

from __future__ import annotations

# Import circulaire volontaire pour démonstration
# Dans vrai projet, ce serait un code smell à corriger
try:
    from . import circular_b  # noqa: F401
except ImportError:
    pass


class ServiceA:
    """Service A qui dépend de B."""

    def __init__(self, name: str = "A"):
        self.name: str = name
        self.b_service: object | None = None

    def set_b(self, b_service) -> None:  # type: ignore[no-untyped-def]
        """Injecte dépendance B."""
        self.b_service = b_service

    def do_work(self) -> str:
        """Travail A."""
        return f"{self.name} working"

    def call_b(self) -> str:
        """Appelle B si disponible."""
        if self.b_service:
            return f"A -> B: {self.b_service.do_work()}"  # type: ignore[attr-defined]
        return "A alone"
