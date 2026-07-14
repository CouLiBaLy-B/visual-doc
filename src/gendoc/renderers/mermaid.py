"""Générateur Mermaid pour diagrammes de classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo, PackageInfo, Visibility

from ..analyzer.models import RelationType


def _filter_by_visibility(cls: "ClassInfo", public_only: bool) -> tuple[list, list]:
    """Filtre attributs/méthodes selon visibilité."""
    if public_only:
        attrs = [a for a in cls.attributes if a.visibility.value == "public"]
        methods = [m for m in cls.methods if m.visibility.value == "public"]
    else:
        attrs = cls.attributes
        methods = cls.methods
    return attrs, methods


def _format_class_mermaid(
    cls: "ClassInfo", public_only: bool = False, max_methods: int | None = None
) -> str:
    attrs, methods = _filter_by_visibility(cls, public_only)
    lines = [f"    class {cls.name} {{"]
    # attributs
    for attr in attrs[:50]:  # limiter
        lines.append(f"        {attr.mermaid_str()}")
    if attrs and methods:
        lines.append(f"        --")
    # méthodes
    method_list = methods
    if max_methods:
        method_list = method_list[:max_methods]
    for method in method_list:
        # ignorer dunder sauf __init__
        if method.name.startswith("__") and method.name != "__init__":
            if public_only:
                continue
        lines.append(f"        {method.mermaid_signature()}")
    lines.append("    }")
    return "\n".join(lines)


def generate_class_diagram_mermaid(
    classes: dict[str, "ClassInfo"],
    relations: list["RelationInfo"],
    public_only: bool = False,
    inheritance_depth: int | None = None,
    title: str | None = None,
) -> str:
    """Génère diagramme de classes Mermaid."""
    lines = ["classDiagram"]
    if title:
        lines[0] = f"classDiagram\n    %% {title}"

    # Option: filtrer héritage depth ? Ici on respecte inheritance_depth en limitant relations
    # Pour simplifier, on affiche toutes les classes et relations filtrées

    # Dédupliquer et trier classes par nom
    sorted_classes = sorted(classes.values(), key=lambda c: c.name)

    # Générer définitions de classes
    for cls in sorted_classes:
        lines.append(_format_class_mermaid(cls, public_only=public_only))

    # Relations
    for rel in relations:
        # résoudre noms simples pour mermaid (utilise noms de classes, pas qualified)
        source_simple = rel.source.split(".")[-1]
        target_simple = rel.target.split(".")[-1]
        if source_simple not in [c.name for c in sorted_classes]:
            continue
        if target_simple not in [c.name for c in sorted_classes]:
            continue

        if rel.relation_type == RelationType.INHERITANCE:
            lines.append(f"    {target_simple} <|-- {source_simple}")
        elif rel.relation_type == RelationType.COMPOSITION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"    {source_simple} *-- {target_simple}{label}")
        elif rel.relation_type == RelationType.AGGREGATION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"    {source_simple} o-- {target_simple}{label}")
        elif rel.relation_type == RelationType.ASSOCIATION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"    {source_simple} --> {target_simple}{label}")
        elif rel.relation_type == RelationType.DEPENDENCY:
            label = f" : {rel.label}" if rel.label else " : depends"
            lines.append(f"    {source_simple} ..> {target_simple}{label}")

    return "\n".join(lines)


def generate_module_class_diagram_mermaid(
    module_name: str,
    classes: list["ClassInfo"],
    all_relations: list["RelationInfo"],
    public_only: bool = False,
) -> str:
    """Diagramme de classes pour un module spécifique."""
    # Filtrer classes du module
    class_map = {c.qualified_name: c for c in classes}
    # Relations internes au module uniquement, plus relations vers externes si souhaité
    # Pour lisibilité, on inclut relations dont source et target sont dans module, plus héritage externe
    module_class_names = {c.name for c in classes}
    # On filtre relations où source dans module
    relevant_relations = []
    for rel in all_relations:
        src_simple = rel.source.split(".")[-1]
        tgt_simple = rel.target.split(".")[-1]
        src_in = src_simple in module_class_names
        tgt_in = tgt_simple in module_class_names
        # inclure si au moins un côté dans module
        if src_in or tgt_in:
            # mais on ne veut que les classes du module + leurs collaborateurs directs
            # Pour diagramme par module, on inclut uniquement si les deux extrémités sont dans module
            # ou si c'est héritage (pour voir parents)
            if src_in and tgt_in:
                relevant_relations.append(rel)
            elif src_in and rel.relation_type == RelationType.INHERITANCE:
                relevant_relations.append(rel)
            elif tgt_in and rel.relation_type == RelationType.INHERITANCE:
                relevant_relations.append(rel)

    # Construire map avec classes du module + éventuellement bases externes comme placeholder?
    # Pour Mermaid, on a besoin des classes externes si relation héritage
    extended_classes = dict(class_map)
    # Ajouter classes externes référencées par héritage si pas déjà présentes (créer stub)
    for rel in relevant_relations:
        if rel.target not in extended_classes:
            # stub
            from ..analyzer.models import ClassInfo
            from pathlib import Path

            # créer classe minimale
            stub = ClassInfo(
                name=rel.target.split(".")[-1],
                module="external",
                file_path=Path("."),
                bases=[],
            )
            extended_classes[rel.target] = stub
        if rel.source not in extended_classes:
            from ..analyzer.models import ClassInfo
            from pathlib import Path

            stub = ClassInfo(
                name=rel.source.split(".")[-1],
                module="external",
                file_path=Path("."),
            )
            extended_classes[rel.source] = stub

    return generate_class_diagram_mermaid(
        extended_classes, relevant_relations, public_only=public_only, title=f"Module {module_name}"
    )
