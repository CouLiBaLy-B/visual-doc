"""Fixtures tests."""

from pathlib import Path

import pytest


@pytest.fixture
def temp_package(tmp_path: Path) -> Path:
    """Crée package temporaire pour tests."""

    pkg_dir = tmp_path / "testpkg"
    pkg_dir.mkdir()

    (pkg_dir / "__init__.py").write_text('"""Test pkg."""\n__version__ = "0.1"\n')

    (pkg_dir / "models.py").write_text(
        '''
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Product:
    """Produit."""
    id: int
    name: str
    price: float

class User:
    """Utilisateur."""
    def __init__(self, email: str, name: str):
        self.email: str = email
        self.name: str = name
        self.active: bool = True

    def greet(self) -> str:
        return f"Hi {self.name}"

class PremiumUser(User):
    """Premium."""
    def __init__(self, email: str, name: str, level: str = "gold"):
        super().__init__(email, name)
        self.level: str = level
        self.bonus: int = 0

@dataclass
class Order:
    """Commande avec composition."""
    id: int
    user: User
    products: List[Product]
    note: Optional[str] = None

    def total(self) -> float:
        return sum(p.price for p in self.products)
'''
    )

    (pkg_dir / "services.py").write_text(
        '''
from .models import User, Order, Product
from typing import List

class UserService:
    """Service user."""
    def __init__(self):
        self.users: List[User] = []

    def create(self, email: str) -> User:
        u = User(email, "Test")
        self.users.append(u)
        return u

class OrderService:
    """Service order dépend de UserService."""
    def __init__(self, user_service: UserService):
        self.user_service: UserService = user_service

    def create_order(self, user: User, products: List[Product]) -> Order:
        return Order(id=1, user=user, products=products)
'''
    )

    (pkg_dir / "circular_a.py").write_text(
        '''
from . import circular_b
class A:
    def __init__(self):
        self.b = None
'''
    )

    (pkg_dir / "circular_b.py").write_text(
        '''
from . import circular_a
class B:
    def __init__(self):
        self.a = None
'''
    )

    return pkg_dir
