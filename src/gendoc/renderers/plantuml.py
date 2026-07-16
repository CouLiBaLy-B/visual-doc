"""Générateur PlantUML."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo

from .common import (
    attribute_plantuml,
    escape_plantuml_note_line,
    filter_members,
    format_relation_edge,
    method_plantuml,
    sanitize_id,
)
from .mermaid import _relations_for_module, extend_with_stubs


def generate_class_diagram_plantuml(
    classes: dict[str, ClassInfo],
    relations: list[RelationInfo],
    public_only: bool = False,
    title: str | None = None,
) -> str:
    """Génère diagramme PlantUML.

    Les classes sont déclarées `class "Nom" as id_qualifié` pour éviter la fusion
    des homonymes entre modules.
    """
    lines = ["@startuml"]
    if title:
        lines.append(f"title {title}")
    lines.append("skinparam classAttributeIconSize 0")
    lines.append("skinparam classFontStyle bold")
    lines.append("hide empty members")

    sorted_classes = sorted(classes.values(), key=lambda c: c.qualified_name)
    node_ids = {c.qualified_name: sanitize_id(c.qualified_name) for c in sorted_classes}

    for cls in sorted_classes:
        node_id = node_ids[cls.qualified_name]
        lines.append(f'class "{cls.name}" as {node_id} {{')
        attrs, methods = filter_members(cls, public_only)
        for attr in attrs:
            lines.append(f"    {attribute_plantuml(attr)}")
        if attrs and methods:
            lines.append("    --")
        for method in methods:
            lines.append(f"    {method_plantuml(method)}")
        lines.append("}")

        if cls.docstring and not public_only:
            first_line = escape_plantuml_note_line(cls.docstring.strip().split("\n")[0][:80])
            lines.append(f"note top of {node_id}")
            lines.append(f"  {first_line}")
            lines.append("end note")

    for rel in relations:
        if rel.source not in node_ids or rel.target not in node_ids:
            continue
        lines.append(format_relation_edge(rel, node_ids[rel.source], node_ids[rel.target]))

    lines.append("@enduml")
    return "\n".join(lines)


def generate_module_class_diagram_plantuml(
    module_name: str,
    classes: list[ClassInfo],
    all_relations: list[RelationInfo],
    public_only: bool = False,
) -> str:
    """Diagramme PlantUML pour un module."""
    class_map = {c.qualified_name: c for c in classes}
    relevant_relations = _relations_for_module(classes, all_relations)
    extended = extend_with_stubs(class_map, relevant_relations)

    return generate_class_diagram_plantuml(
        extended, relevant_relations, public_only=public_only, title=f"Module {module_name}"
    )
