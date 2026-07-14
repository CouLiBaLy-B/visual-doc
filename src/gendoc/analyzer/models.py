"""Modèles de données pour l'analyse statique."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class Visibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    DUNDER = "dunder"


class RelationType(str, Enum):
    INHERITANCE = "inheritance"
    COMPOSITION = "composition"
    ASSOCIATION = "association"
    DEPENDENCY = "dependency"
    AGGREGATION = "aggregation"


@dataclass
class AttributeInfo:
    """Représente un attribut de classe."""

    name: str
    type_annotation: Optional[str] = None
    default: Optional[str] = None
    visibility: Visibility = Visibility.PUBLIC
    is_class_attribute: bool = False
    docstring: Optional[str] = None

    def is_private(self) -> bool:
        return self.visibility in (Visibility.PRIVATE, Visibility.DUNDER)

    def mermaid_str(self) -> str:
        type_part = f" {self.type_annotation}" if self.type_annotation else ""
        visibility_char = {"public": "+", "private": "-", "protected": "#", "dunder": "+"}.get(
            self.visibility.value, "+"
        )
        return f"{visibility_char}{self.name}{type_part}"

    def plantuml_str(self) -> str:
        type_part = f" : {self.type_annotation}" if self.type_annotation else ""
        visibility_char = {"public": "+", "private": "-", "protected": "#", "dunder": "+"}.get(
            self.visibility.value, "+"
        )
        return f"{visibility_char} {self.name}{type_part}"


@dataclass
class MethodInfo:
    """Représente une méthode de classe."""

    name: str
    parameters: list[tuple[str, Optional[str]]] = field(default_factory=list)  # (name, type)
    return_type: Optional[str] = None
    visibility: Visibility = Visibility.PUBLIC
    is_static: bool = False
    is_classmethod: bool = False
    is_property: bool = False
    is_abstract: bool = False
    docstring: Optional[str] = None

    def is_private(self) -> bool:
        return self.visibility in (Visibility.PRIVATE, Visibility.DUNDER)

    def mermaid_signature(self) -> str:
        visibility_char = {"public": "+", "private": "-", "protected": "#", "dunder": "+"}.get(
            self.visibility.value, "+"
        )
        params = ", ".join([f"{n}: {t}" if t else n for n, t in self.parameters if n != "self"])
        ret = f" {self.return_type}" if self.return_type else ""
        stereotype = ""
        if self.is_static:
            stereotype = "<<static>> "
        elif self.is_classmethod:
            stereotype = "<<classmethod>> "
        return f"{visibility_char}{stereotype}{self.name}({params}){ret}"

    def plantuml_signature(self) -> str:
        visibility_char = {"public": "+", "private": "-", "protected": "#", "dunder": "+"}.get(
            self.visibility.value, "+"
        )
        params = ", ".join([f"{n}: {t}" if t else n for n, t in self.parameters if n != "self"])
        ret = f" : {self.return_type}" if self.return_type else ""
        stereotype = ""
        if self.is_static:
            stereotype = "{static} "
        elif self.is_classmethod:
            stereotype = "{static} "
        return f"{visibility_char} {stereotype}{self.name}({params}){ret}"


@dataclass
class ClassInfo:
    """Représente une classe Python analysée."""

    name: str
    module: str
    file_path: Path
    bases: list[str] = field(default_factory=list)
    attributes: list[AttributeInfo] = field(default_factory=list)
    methods: list[MethodInfo] = field(default_factory=list)
    docstring: Optional[str] = None
    line_number: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}"

    def public_attributes(self) -> list[AttributeInfo]:
        return [a for a in self.attributes if a.visibility == Visibility.PUBLIC]

    def public_methods(self) -> list[MethodInfo]:
        return [m for m in self.methods if m.visibility == Visibility.PUBLIC]


@dataclass
class ModuleInfo:
    """Représente un module Python."""

    name: str
    file_path: Path
    dotted_path: str
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)  # modules importés
    internal_imports: list[str] = field(default_factory=list)  # imports internes au projet
    external_imports: list[str] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class RelationInfo:
    """Relation entre deux classes."""

    source: str  # qualified name
    target: str
    relation_type: RelationType
    label: Optional[str] = None
    source_cardinality: Optional[str] = None
    target_cardinality: Optional[str] = None


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


def get_visibility(name: str) -> Visibility:
    """Détermine la visibilité d'un nom."""
    if name.startswith("__") and name.endswith("__"):
        return Visibility.DUNDER
    if name.startswith("__"):
        return Visibility.PRIVATE
    if name.startswith("_"):
        return Visibility.PROTECTED
    return Visibility.PUBLIC
