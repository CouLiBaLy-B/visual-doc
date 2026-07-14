"""Utilitaires - Fonctions helpers."""

from __future__ import annotations

import re
from typing import List


def format_price(amount: float, currency: str = "EUR") -> str:
    """Formate prix avec devise.

    Args:
        amount: Montant.
        currency: Devise.

    Returns:
        Chaîne formatée, ex: "10.00 EUR".

    Examples:
        >>> format_price(10)
        '10.00 EUR'
        >>> format_price(5.5, "USD")
        '5.50 USD'
    """
    return f"{amount:.2f} {currency}"


def validate_email(email: str) -> bool:
    """Valide email avec regex simple.

    Args:
        email: Email à valider.

    Returns:
        True si valide.
    """
    pattern = r"^[^@]+@[^@]+\.[^@]+$"
    return bool(re.match(pattern, email))


def slugify(text: str) -> str:
    """Convertit texte en slug.

    Args:
        text: Texte source.

    Returns:
        Slug.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def chunk_list(items: List, size: int) -> List[List]:
    """Découpe liste en chunks.

    Args:
        items: Liste à découper.
        size: Taille chunk.

    Returns:
        Liste de chunks.
    """
    return [items[i : i + size] for i in range(0, len(items), size)]


class CacheManager:
    """Gestionnaire cache simple.

    Attributes:
        max_size: Taille max cache.
        _store: Stockage interne.
    """

    def __init__(self, max_size: int = 100):
        self.max_size: int = max_size
        self._store: dict[str, object] = {}

    def get(self, key: str) -> object | None:
        """Récupère valeur du cache."""
        return self._store.get(key)

    def set(self, key: str, value: object) -> None:
        """Stocke valeur."""
        if len(self._store) >= self.max_size:
            # FIFO simple
            first = next(iter(self._store))
            del self._store[first]
        self._store[key] = value

    def clear(self) -> None:
        """Vide cache."""
        self._store.clear()
