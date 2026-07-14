"""Services métier - Démonstration dépendances."""

from __future__ import annotations

from typing import List, Optional

from .models import Order, Product, User
from .utils import format_price, validate_email


class UserService:
    """Service gestion utilisateurs.

    Attributes:
        users: Liste des utilisateurs en mémoire.
    """

    def __init__(self):
        self.users: List[User] = []
        self._cache: dict[int, User] = {}

    def create_user(self, email: str, name: str) -> User:
        """Crée un utilisateur.

        Args:
            email: Email utilisateur.
            name: Nom utilisateur.

        Returns:
            Utilisateur créé.

        Raises:
            ValueError: Si email invalide.
        """
        if not validate_email(email):
            raise ValueError(f"Email invalide: {email}")
        user = User(id=len(self.users) + 1, email=email, name=name)
        self.users.append(user)
        self._cache[user.id] = user
        return user

    def find_by_email(self, email: str) -> Optional[User]:
        """Trouve utilisateur par email."""
        for u in self.users:
            if u.email == email:
                return u
        return None

    def list_users(self) -> List[User]:
        """Liste tous les utilisateurs."""
        return self.users.copy()


class OrderService:
    """Service gestion commandes - Dépend de UserService et Product.

    Attributes:
        user_service: Service utilisateurs (association).
        orders: Liste commandes.
    """

    def __init__(self, user_service: UserService):
        self.user_service: UserService = user_service
        self.orders: List[Order] = []
        self.products: List[Product] = []

    def add_product(self, product: Product) -> None:
        """Ajoute produit au catalogue."""
        self.products.append(product)

    def create_order(self, user_id: int) -> Order:
        """Crée commande pour utilisateur.

        Args:
            user_id: ID utilisateur.

        Returns:
            Commande créée.
        """
        user = self.user_service._cache.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        order = Order(id=len(self.orders) + 1, user=user)
        self.orders.append(order)
        return order

    def get_order_summary(self, order: Order) -> str:
        """Génère résumé commande avec prix formaté."""
        total = order.total_amount()
        return f"Commande {order.id} - {format_price(total)} pour {order.user.name}"

    def process_payment(self, order: Order) -> bool:
        """Simule paiement.

        Args:
            order: Commande à payer.

        Returns:
            True si succès.
        """
        if order.total_amount() <= 0:
            return False
        order.set_status("paid")
        return True
