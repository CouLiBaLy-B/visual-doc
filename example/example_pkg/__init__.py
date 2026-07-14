"""Example package pour démontrer gendoc.

Ce package montre:
- Héritage
- Composition / Association
- Dépendances circulaires (signalées en rouge)
- Docstrings Google style
"""

from .models import User, Product, Order, PremiumUser
from .services import OrderService, UserService
from .utils import format_price, validate_email

__all__ = [
    "User",
    "Product",
    "Order",
    "PremiumUser",
    "OrderService",
    "UserService",
    "format_price",
    "validate_email",
]

__version__ = "0.1.0"
