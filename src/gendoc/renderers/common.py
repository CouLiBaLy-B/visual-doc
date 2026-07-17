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

from ..analyzer.models import RelationType, Visibility

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


# Stéréotype de classe (analyzer) -> libellé UML affiché entre <<...>>.
_STEREOTYPE_LABELS = {"enum": "enumeration", "dataclass": "dataclass"}


def stereotype_label(stereotype: str | None) -> str | None:
    """Libellé UML d'un stéréotype de classe, ou None s'il n'y a rien à afficher."""
    if stereotype is None:
        return None
    return _STEREOTYPE_LABELS.get(stereotype, stereotype)


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


# Homoglyphes visuellement fidèles pour les caractères que la grammaire des
# membres Mermaid ne tolère pas : `|` des unions (hors grammaire) et `,` à
# l'intérieur des génériques ~...~ (explicitement interdite par Mermaid).
_MERMAID_TYPE_TRANS = str.maketrans(
    {
        "[": "~",  # génériques : syntaxe Mermaid X~Y~
        "]": "~",
        "{": "(",  # une accolade fermerait le bloc de classe
        "}": ")",
        "|": "¦",  # ¦ BROKEN BAR
        ",": "‚",  # ‚ SINGLE LOW-9 QUOTATION MARK
    }
)


def escape_mermaid_type(type_str: str) -> str:
    """Adapte une annotation de type Python à la syntaxe des membres Mermaid.

    À appliquer aux annotations uniquement, jamais à la ligne de membre
    complète (les virgules *entre* paramètres sont légales en Mermaid).
    """
    return type_str.translate(_MERMAID_TYPE_TRANS)


# --- Formatage des membres (attributs / méthodes) par cible -------------------

_VISIBILITY_CHARS: dict[Visibility, str] = {
    Visibility.PUBLIC: "+",
    Visibility.PRIVATE: "-",
    Visibility.PROTECTED: "#",
    Visibility.DUNDER: "+",
}


def visibility_char(visibility: Visibility) -> str:
    return _VISIBILITY_CHARS.get(visibility, "+")


def _method_display_name(method: MethodInfo) -> str:
    return f"async {method.name}" if method.is_async else method.name


def attribute_mermaid(attr: AttributeInfo) -> str:
    type_part = f" {escape_mermaid_type(attr.type_annotation)}" if attr.type_annotation else ""
    return f"{visibility_char(attr.visibility)}{attr.name}{type_part}"


def attribute_plain(attr: AttributeInfo) -> str:
    """Représentation texte brut (SVG), types non transformés."""
    type_part = f" {attr.type_annotation}" if attr.type_annotation else ""
    return f"{visibility_char(attr.visibility)}{attr.name}{type_part}"


def attribute_plantuml(attr: AttributeInfo) -> str:
    type_part = f" : {attr.type_annotation}" if attr.type_annotation else ""
    return f"{visibility_char(attr.visibility)} {attr.name}{type_part}"


def method_mermaid(method: MethodInfo) -> str:
    params = ", ".join(
        f"{n}: {escape_mermaid_type(t)}" if t else n
        for n, t in method.parameters
        if n != "self"
    )
    ret = f" {escape_mermaid_type(method.return_type)}" if method.return_type else ""
    stereotype = ""
    if method.is_static:
        stereotype = "<<static>> "
    elif method.is_classmethod:
        stereotype = "<<classmethod>> "
    return (
        f"{visibility_char(method.visibility)}{stereotype}"
        f"{_method_display_name(method)}({params}){ret}"
    )


def method_plain(method: MethodInfo) -> str:
    """Représentation texte brut (SVG), types non transformés."""
    params = ", ".join(f"{n}: {t}" if t else n for n, t in method.parameters if n != "self")
    ret = f" {method.return_type}" if method.return_type else ""
    return f"{visibility_char(method.visibility)}{_method_display_name(method)}({params}){ret}"


def method_plantuml(method: MethodInfo) -> str:
    params = ", ".join(f"{n}: {t}" if t else n for n, t in method.parameters if n != "self")
    ret = f" : {method.return_type}" if method.return_type else ""
    stereotype = ""
    if method.is_static or method.is_classmethod:
        stereotype = "{static} "
    elif method.is_abstract:
        stereotype = "{abstract} "
    return (
        f"{visibility_char(method.visibility)} {stereotype}"
        f"{_method_display_name(method)}({params}){ret}"
    )
