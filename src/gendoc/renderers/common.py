"""Éléments de rendu partagés entre les renderers (Mermaid, PlantUML, SVG).

Source unique pour : identifiants de nœuds, filtres de visibilité, table
relation→glyphe, arêtes du graphe de packages et fonctions d'échappement
par cible. Ce module ne doit importer que ``analyzer.models``, jamais un
renderer.
"""

from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from ..analyzer.models import RelationType

if TYPE_CHECKING:
    from ..analyzer.models import (
        AttributeInfo,
        ClassInfo,
        MethodInfo,
        PackageInfo,
        RelationInfo,
    )


def sanitize_id(qualified_name: str) -> str:
    """Transforme un nom qualifié en identifiant de nœud valide (Mermaid/PlantUML)."""
    return re.sub(r"[^0-9A-Za-z_]", "_", qualified_name)


def filter_members(
    cls: ClassInfo, public_only: bool
) -> tuple[list[AttributeInfo], list[MethodInfo]]:
    """Filtre attributs/méthodes selon visibilité."""
    if public_only:
        attrs = [a for a in cls.attributes if a.visibility.value == "public"]
        methods = [m for m in cls.methods if m.visibility.value == "public"]
    else:
        attrs = cls.attributes
        methods = cls.methods
    return attrs, methods


# Table unique relation -> glyphe, partagée par les renderers texte.
_RELATION_GLYPHS: dict[RelationType, str] = {
    RelationType.INHERITANCE: "<|--",  # émise inversée : target <|-- source
    RelationType.COMPOSITION: "*--",
    RelationType.AGGREGATION: "o--",
    RelationType.ASSOCIATION: "-->",
    RelationType.DEPENDENCY: "..>",
}


def format_relation_edge(
    rel: RelationInfo,
    src_id: str,
    tgt_id: str,
    *,
    default_dependency_label: str | None = None,
) -> str:
    """Arête UML texte pour une relation (syntaxe commune Mermaid/PlantUML).

    L'héritage est émis inversé (``target <|-- source``) et sans label ;
    ``default_dependency_label`` s'applique aux dépendances sans label.
    """
    glyph = _RELATION_GLYPHS[rel.relation_type]
    if rel.relation_type == RelationType.INHERITANCE:
        return f"{tgt_id} {glyph} {src_id}"
    label = rel.label
    if rel.relation_type == RelationType.DEPENDENCY and not label:
        label = default_dependency_label
    label_part = f" : {label}" if label else ""
    return f"{src_id} {glyph} {tgt_id}{label_part}"


def circular_edge_set(
    circular_dependencies: list[list[str]],
) -> tuple[set[str], set[tuple[str, str]]]:
    """Noeuds et arêtes orientées des cycles (y compris l'arête de fermeture)."""
    nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    for cycle in circular_dependencies:
        for i in range(len(cycle)):
            src = cycle[i]
            tgt = cycle[(i + 1) % len(cycle)]
            if src == tgt:
                continue
            nodes.add(src)
            nodes.add(tgt)
            edges.add((src, tgt))
    return nodes, edges


def sorted_package_edges(package_info: PackageInfo) -> list[tuple[str, str]]:
    """Arêtes internes du graphe de dépendances, en ordre déterministe.

    L'ordre est stable et sert d'index (``linkStyle`` Mermaid) : ne pas le changer.
    """
    return [
        (src, tgt)
        for src in sorted(package_info.dependencies)
        for tgt in sorted(package_info.dependencies[src])
        if tgt in package_info.modules
    ]


def escape_svg_text(text: str) -> str:
    """Échappement pour contenu texte SVG/XML."""
    return html.escape(text)


def escape_plantuml_note_line(text: str) -> str:
    """Neutralise un contenu de note qui terminerait le bloc (`end note`)."""
    return re.sub(r"end\s*note", "end_note", text, flags=re.IGNORECASE)
