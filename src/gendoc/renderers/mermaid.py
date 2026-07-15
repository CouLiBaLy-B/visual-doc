"""Générateur Mermaid pour diagrammes de classes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo

from ..analyzer.models import ClassInfo as _ClassInfo
from ..analyzer.models import RelationType


def sanitize_id(qualified_name: str) -> str:
    """Transforme un nom qualifié en identifiant de nœud valide (Mermaid/PlantUML)."""
    return re.sub(r"[^0-9A-Za-z_]", "_", qualified_name)


def _filter_by_visibility(cls: ClassInfo, public_only: bool) -> tuple[list, list]:
    """Filtre attributs/méthodes selon visibilité."""
    if public_only:
        attrs = [a for a in cls.attributes if a.visibility.value == "public"]
        methods = [m for m in cls.methods if m.visibility.value == "public"]
    else:
        attrs = cls.attributes
        methods = cls.methods
    return attrs, methods


def _format_class_mermaid(
    cls: ClassInfo,
    node_id: str,
    public_only: bool = False,
    max_methods: int | None = None,
) -> str:
    attrs, methods = _filter_by_visibility(cls, public_only)
    lines = [f'    class {node_id}["{cls.name}"] {{']
    for attr in attrs[:50]:  # limiter
        lines.append(f"        {attr.mermaid_str()}")
    method_list = methods[:max_methods] if max_methods else methods
    for method in method_list:
        lines.append(f"        {method.mermaid_signature()}")
    lines.append("    }")
    return "\n".join(lines)


def generate_class_diagram_mermaid(
    classes: dict[str, ClassInfo],
    relations: list[RelationInfo],
    public_only: bool = False,
    title: str | None = None,
) -> str:
    """Génère diagramme de classes Mermaid.

    Les nœuds sont identifiés par leur nom qualifié sanitisé (pas de fusion
    entre classes homonymes de modules différents) et affichés avec leur nom court.
    """
    lines = ["classDiagram"]
    if title:
        lines[0] = f"classDiagram\n    %% {title}"

    sorted_classes = sorted(classes.values(), key=lambda c: c.qualified_name)
    node_ids = {c.qualified_name: sanitize_id(c.qualified_name) for c in sorted_classes}

    # Un classDiagram réduit à l'en-tête + un commentaire est rejeté par Mermaid
    # (« Syntax error in text ») : émettre une note pour garder un diagramme valide.
    if not sorted_classes:
        lines.append('    note "Aucune classe à afficher"')
        return "\n".join(lines)

    for cls in sorted_classes:
        lines.append(
            _format_class_mermaid(cls, node_ids[cls.qualified_name], public_only=public_only)
        )

    for rel in relations:
        if rel.source not in node_ids or rel.target not in node_ids:
            continue
        src = node_ids[rel.source]
        tgt = node_ids[rel.target]
        label = f" : {rel.label}" if rel.label else ""

        if rel.relation_type == RelationType.INHERITANCE:
            lines.append(f"    {tgt} <|-- {src}")
        elif rel.relation_type == RelationType.COMPOSITION:
            lines.append(f"    {src} *-- {tgt}{label}")
        elif rel.relation_type == RelationType.AGGREGATION:
            lines.append(f"    {src} o-- {tgt}{label}")
        elif rel.relation_type == RelationType.ASSOCIATION:
            lines.append(f"    {src} --> {tgt}{label}")
        elif rel.relation_type == RelationType.DEPENDENCY:
            lines.append(f"    {src} ..> {tgt}{label or ' : depends'}")

    return "\n".join(lines)


def _relations_for_module(
    classes: list[ClassInfo],
    all_relations: list[RelationInfo],
) -> list[RelationInfo]:
    """Relations internes au module + héritages entrants/sortants (par nom qualifié)."""
    module_qualified = {c.qualified_name for c in classes}
    relevant: list[RelationInfo] = []
    for rel in all_relations:
        src_in = rel.source in module_qualified
        tgt_in = rel.target in module_qualified
        if src_in and tgt_in:
            relevant.append(rel)
        elif (src_in or tgt_in) and rel.relation_type == RelationType.INHERITANCE:
            relevant.append(rel)
    return relevant


def extend_with_stubs(
    class_map: dict[str, ClassInfo],
    relations: list[RelationInfo],
) -> dict[str, ClassInfo]:
    """Ajoute des classes stub pour les extrémités de relations hors du module."""
    extended = dict(class_map)
    for rel in relations:
        for endpoint in (rel.source, rel.target):
            if endpoint not in extended:
                module, _, name = endpoint.rpartition(".")
                extended[endpoint] = _ClassInfo(
                    name=name or endpoint,
                    module=module or "external",
                    file_path=Path("."),
                )
    return extended


def generate_module_class_diagram_mermaid(
    module_name: str,
    classes: list[ClassInfo],
    all_relations: list[RelationInfo],
    public_only: bool = False,
) -> str:
    """Diagramme de classes pour un module spécifique."""
    class_map = {c.qualified_name: c for c in classes}
    relevant_relations = _relations_for_module(classes, all_relations)
    extended_classes = extend_with_stubs(class_map, relevant_relations)

    return generate_class_diagram_mermaid(
        extended_classes, relevant_relations, public_only=public_only, title=f"Module {module_name}"
    )
