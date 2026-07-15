"""Générateur PlantUML."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo

from ..analyzer.models import RelationType
from .mermaid import _relations_for_module, extend_with_stubs, sanitize_id


def _sanitize_note_line(text: str) -> str:
    """Neutralise un contenu de note qui terminerait le bloc (`end note`)."""
    return re.sub(r"end\s*note", "end_note", text, flags=re.IGNORECASE)


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
        attrs = cls.attributes
        if public_only:
            attrs = [a for a in attrs if a.visibility.value == "public"]
        for attr in attrs:
            lines.append(f"    {attr.plantuml_str()}")
        methods = cls.methods
        if public_only:
            methods = [m for m in methods if m.visibility.value == "public"]
        if attrs and methods:
            lines.append("    --")
        for method in methods:
            lines.append(f"    {method.plantuml_signature()}")
        lines.append("}")

        if cls.docstring and not public_only:
            first_line = _sanitize_note_line(cls.docstring.strip().split("\n")[0][:80])
            lines.append(f"note top of {node_id}")
            lines.append(f"  {first_line}")
            lines.append("end note")

    for rel in relations:
        if rel.source not in node_ids or rel.target not in node_ids:
            continue
        src = node_ids[rel.source]
        tgt = node_ids[rel.target]
        label = f" : {rel.label}" if rel.label else ""

        if rel.relation_type == RelationType.INHERITANCE:
            lines.append(f"{tgt} <|-- {src}")
        elif rel.relation_type == RelationType.COMPOSITION:
            lines.append(f"{src} *-- {tgt}{label}")
        elif rel.relation_type == RelationType.AGGREGATION:
            lines.append(f"{src} o-- {tgt}{label}")
        elif rel.relation_type == RelationType.ASSOCIATION:
            lines.append(f"{src} --> {tgt}{label}")
        elif rel.relation_type == RelationType.DEPENDENCY:
            lines.append(f"{src} ..> {tgt}{label}")

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
