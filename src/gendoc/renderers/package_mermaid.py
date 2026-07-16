"""Générateur de diagrammes de packages / dépendances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import PackageInfo

from .common import circular_edge_set, sanitize_id, sorted_package_edges


def generate_package_diagram_mermaid(
    package_info: PackageInfo,
    highlight_circular: bool = True,
) -> str:
    """Génère diagramme de packages Mermaid flowchart."""

    lines = ["flowchart TD"]

    modules_sorted = sorted(package_info.modules.keys())

    circular_nodes: set[str] = set()
    circular_edges: set[tuple[str, str]] = set()
    if highlight_circular and package_info.circular_dependencies:
        circular_nodes, circular_edges = circular_edge_set(package_info.circular_dependencies)

    for mod in modules_sorted:
        lines.append(f"    {sanitize_id(mod)}[{mod.split('.')[-1]}]")

    lines.append("")

    # une seule liste d'arêtes : sert à la fois à l'émission et aux indices linkStyle
    edges = sorted_package_edges(package_info)
    for src, tgt in edges:
        if (src, tgt) in circular_edges:
            lines.append(f"    {sanitize_id(src)} -->|circular| {sanitize_id(tgt)}")
        else:
            lines.append(f"    {sanitize_id(src)} --> {sanitize_id(tgt)}")

    if circular_nodes:
        lines.append("")
        for node in sorted(circular_nodes):
            lines.append(
                f"    style {sanitize_id(node)} fill:#ffcccc,stroke:#ff0000,stroke-width:2px"
            )
        for idx, (src, tgt) in enumerate(edges):
            if (src, tgt) in circular_edges:
                lines.append(f"    linkStyle {idx} stroke:#ff0000,stroke-width:2px")

    return "\n".join(lines)


def generate_package_diagram_plantuml(package_info: PackageInfo) -> str:
    """Génère diagramme de packages PlantUML."""

    lines = ["@startuml"]
    lines.append(f"title Package Diagram - {package_info.name}")
    lines.append("skinparam packageStyle rectangle")

    lines.append(f"package {package_info.name} {{")
    for mod in sorted(package_info.modules.keys()):
        lines.append(f"  [{mod}] as {sanitize_id(mod)}")
    lines.append("}")

    _, circular_edges = circular_edge_set(package_info.circular_dependencies)

    for src, tgt in sorted_package_edges(package_info):
        src_id = sanitize_id(src)
        tgt_id = sanitize_id(tgt)
        if (src, tgt) in circular_edges:
            lines.append(f"{src_id} .[#red].> {tgt_id} : circulaire")
        else:
            lines.append(f"{src_id} ..> {tgt_id}")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_package_summary_markdown(package_info: PackageInfo) -> str:
    """Génère résumé markdown des dépendances."""

    lines = [f"# Structure du package {package_info.name}", ""]
    lines.append(f"Total modules: {len(package_info.modules)}")
    lines.append(f"Total classes: {len(package_info.classes)}")
    lines.append(f"Total relations: {len(package_info.relations)}")
    lines.append("")

    if package_info.circular_dependencies:
        from ..analyzer.relationships import cycle_display

        lines.append("## ⚠️ Dépendances circulaires détectées")
        lines.append("")
        for idx, cycle in enumerate(package_info.circular_dependencies, 1):
            lines.append(f"{idx}. {cycle_display(cycle)}")
        lines.append("")

    lines.append("## Modules")
    for mod_name, mod_info in sorted(package_info.modules.items()):
        lines.append(
            f"- `{mod_name}` ({len(mod_info.classes)} classes, "
            f"{len(mod_info.internal_imports)} imports internes)"
        )

    lines.append("")
    lines.append("## Dépendances")
    for src, deps in sorted(package_info.dependencies.items()):
        if deps:
            lines.append(f"- `{src}` dépend de: {', '.join(f'`{d}`' for d in sorted(deps))}")

    return "\n".join(lines)
