"""Modèles de données pour l'analyse statique."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


class Visibility(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    DUNDER = "dunder"


class RelationType(StrEnum):
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    ASSOCIATION = "association"
    DEPENDENCY = "dependency"
    AGGREGATION = "aggregation"


@dataclass
class AttributeInfo:
    """Représente un attribut de classe."""

    name: str
    type_annotation: str | None = None
    default: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    is_class_attribute: bool = False


@dataclass
class MethodInfo:
    """Représente une méthode de classe."""

    name: str
    parameters: list[tuple[str, str | None]] = field(default_factory=list)  # (name, type)
    return_type: str | None = None
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False
    is_abstract: bool = False
    is_async: bool = False
    defaults: dict[str, str] = field(default_factory=dict)  # param -> valeur par défaut
    docstring: str | None = None


@dataclass
class ClassInfo:
    """Représente une classe Python analysée."""

    name: str
    module: str
    file_path: Path
    bases: list[str] = field(default_factory=list)
    attributes: list[AttributeInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    docstring: str | None = None
    line_number: int = 0
    stereotype: str | None = None  # "enum" | "dataclass" | None

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}"


@dataclass
class ModuleInfo:
    """Représente un module Python."""

    name: str
    file_path: Path
    dotted_path: str
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[MethodInfo] = field(default_factory=list)  # fonctions top-level
    imports: list[str] = field(default_factory=list)  # modules importés
    internal_imports: list[str] = field(default_factory=list)  # imports internes au projet
    external_imports: list[str] = field(default_factory=list)
    docstring: str | None = None


@dataclass
class RelationInfo:
    """Relation entre deux classes."""

    source: str  # qualified name
    target: str
    relation_type: RelationType
    label: str | None = None


@dataclass
class PackageInfo:
    """Représente un package analysé."""

    name: str
    root_path: Path
    modules: dict[str, ModuleInfo] = field(default_factory=dict)  # dotted_path -> info
    classes: dict[str, ClassInfo] = field(default_factory=dict)  # qualified_name -> info
    relations: list[RelationInfo] = field(default_factory=list)
    dependencies: dict[str, set[str]] = field(default_factory=dict)  # module -> dependencies
    circular_dependencies: list[list[str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)  # fichiers ignorés (mode tolérant)
    warnings: list[str] = field(default_factory=list)  # avertissements non bloquants


def get_visibility(name: str) -> Visibility:
    """Détermine la visibilité d'un nom."""
    if name.startswith("__") and name.endswith("__"):
        return Visibility.DUNDER
    if name.startswith("__"):
        return Visibility.PRIVATE
    if name.startswith("_"):
        return Visibility.PROTECTED
    return Visibility.PUBLIC
