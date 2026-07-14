"""Modèles de domaine - Exemple pour gendoc."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Product:
    """Représente un produit.

    Attributes:
        id: Identifiant unique du produit.
        name: Nom du produit.
        price: Prix unitaire.
        stock: Quantité en stock.
    """

    id: int
    name: str
    price: float
    stock: int = 0
    description: Optional[str] = None

    def is_available(self) -> bool:
        """Vérifie si produit disponible.

        Returns:
            True si stock > 0.
        """
        return self.stock > 0

    def apply_discount(self, percent: float) -> float:
        """Applique une remise.

        Args:
            percent: Pourcentage de remise (0-100).

        Returns:
            Nouveau prix après remise.
        """
        return self.price * (1 - percent / 100)


@dataclass
class User:
    """Utilisateur de base.

    Attributes:
        id: Identifiant utilisateur.
        email: Adresse email.
        name: Nom complet.
        created_at: Date de création.
    """

    id: int
    email: str
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    _password_hash: str = field(default="", repr=False)

    def greet(self) -> str:
        """Retourne message d'accueil.

        Returns:
            Message personnalisé.
        """
        return f"Bonjour {self.name}!"

    def _validate(self) -> bool:
        """Validation interne (méthode privée)."""
        return "@" in self.email

    @property
    def is_active(self) -> bool:
        """Vérifie si utilisateur actif."""
        return bool(self._password_hash)


class PremiumUser(User):
    """Utilisateur premium avec avantages.

    Cette classe démontre l'héritage.
    Hérite de User et ajoute fonctionnalités premium.
    """

    def __init__(self, id: int, email: str, name: str, membership_level: str = "gold"):
        super().__init__(id, email, name)
        self.membership_level: str = membership_level
        self.bonus_points: int = 0
        self._vip_code: str = "VIP123"

    def add_points(self, points: int) -> None:
        """Ajoute points bonus.

        Args:
            points: Nombre de points à ajouter.
        """
        self.bonus_points += points

    def get_discount(self) -> float:
        """Retourne remise selon niveau.

        Returns:
            Pourcentage de remise.
        """
        levels = {"silver": 5, "gold": 10, "platinum": 20}
        return levels.get(self.membership_level, 0)


@dataclass
class OrderItem:
    """Ligne de commande - Composition avec Product.

    Attributes:
        product: Produit commandé (composition).
        quantity: Quantité.
    """

    product: Product
    quantity: int

    @property
    def total(self) -> float:
        """Total ligne."""
        return self.product.price * self.quantity


@dataclass
class Order:
    """Commande - Association et composition.

    Attributes:
        id: Identifiant commande.
        user: Utilisateur ayant passé commande (association).
        items: Lignes de commande (composition).
        status: Statut commande.
    """

    id: int
    user: User
    items: List[OrderItem] = field(default_factory=list)
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

    def add_item(self, product: Product, quantity: int) -> OrderItem:
        """Ajoute un produit à la commande.

        Args:
            product: Produit à ajouter.
            quantity: Quantité.

        Returns:
            La ligne créée.
        """
        item = OrderItem(product=product, quantity=quantity)
        self.items.append(item)
        return item

    def total_amount(self) -> float:
        """Calcule montant total.

        Returns:
            Somme de tous les items.
        """
        return sum(item.total for item in self.items)

    def set_status(self, new_status: str) -> None:
        """Change statut.

        Args:
            new_status: Nouveau statut.
        """
        self.status = new_status
