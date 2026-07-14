"""Générateur de diagrammes de packages / dépendances."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import PackageInfo


def generate_package_diagram_mermaid(
    package_info: "PackageInfo",
    highlight_circular: bool = True,
) -> str:
    """Génère diagramme de packages Mermaid flowchart."""

    lines = ["flowchart TD"]

    # Noeuds
    modules_sorted = sorted(package_info.modules.keys())

    # Déterminer les noeuds impliqués dans cycles pour coloration
    circular_nodes: set[str] = set()
    circular_edges: set[tuple[str, str]] = set()
    if highlight_circular and package_info.circular_dependencies:
        for cycle in package_info.circular_dependencies:
            for i in range(len(cycle) - 1):
                src = cycle[i]
                tgt = cycle[i + 1]
                circular_nodes.add(src)
                circular_nodes.add(tgt)
                circular_edges.add((src, tgt))
                circular_edges.add((tgt, src))  # aussi reverse pour recherche simple
            # fermer cycle
            if len(cycle) > 1:
                circular_nodes.add(cycle[-1])

    # Sanitiser noms pour mermaid id: remplacer '.' et '-' par '_'
    def sanitize(name: str) -> str:
        return name.replace(".", "_").replace("-", "_").replace("/", "_")

    # Générer noeuds avec alias
    for mod in modules_sorted:
        mod_sanitized = sanitize(mod)
        display = mod.split(".")[-1] if "." in mod else mod
        # avec fichier ?
        # Ajouter style différent si circular
        lines.append(f"    {mod_sanitized}[{display}]")

    lines.append("")

    # Arêtes
    for src, deps in package_info.dependencies.items():
        for tgt in deps:
            if tgt not in package_info.modules:
                continue
            src_s = sanitize(src)
            tgt_s = sanitize(tgt)
            if (src, tgt) in circular_edges:
                lines.append(f"    {src_s} -->|circular| {tgt_s}")
            else:
                lines.append(f"    {src_s} --> {tgt_s}")

    # Styles pour circulaires en rouge
    if circular_nodes:
        lines.append("")
        for node in circular_nodes:
            node_s = sanitize(node)
            lines.append(f"    style {node_s} fill:#ffcccc,stroke:#ff0000,stroke-width:2px")

        # Lier circulaires en rouge
        # mermaid linkStyle
        # on doit indexer edges
        edge_index = 0
        edge_style_lines = []
        all_edges = []
        for src, deps in package_info.dependencies.items():
            for tgt in deps:
                if tgt not in package_info.modules:
                    continue
                all_edges.append((src, tgt))

        for idx, (src, tgt) in enumerate(all_edges):
            if (src, tgt) in circular_edges:
                edge_style_lines.append(f"    linkStyle {idx} stroke:#ff0000,stroke-width:2px")

        lines.extend(edge_style_lines)

    return "\n".join(lines)


def generate_package_diagram_plantuml(package_info: "PackageInfo") -> str:
    """Génère diagramme de packages PlantUML."""

    lines = ["@startuml"]
    lines.append(f"title Package Diagram - {package_info.name}")
    lines.append("skinparam packageStyle rectangle")

    # Créer packages
    # Group by top-level
    lines.append(f"package {package_info.name} {{")

    modules_sorted = sorted(package_info.modules.keys())
    for mod in modules_sorted:
        # afficher comme component
        display = mod
        lines.append(f"  [{display}] as {mod.replace('.', '_')}")

    lines.append("}")

    # Dépendances
    for src, deps in package_info.dependencies.items():
        for tgt in deps:
            if tgt not in package_info.modules:
                continue
            src_id = src.replace(".", "_")
            tgt_id = tgt.replace(".", "_")
            # check circular
            is_circular = any(src in cycle and tgt in cycle for cycle in package_info.circular_dependencies)
            if is_circular:
                lines.append(f"{src_id} ..> {tgt_id} #red : circular")
            else:
                lines.append(f"{src_id} ..> {tgt_id}")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_package_summary_markdown(package_info: "PackageInfo") -> str:
    """Génère résumé markdown des dépendances."""

    lines = [f"# Structure du package {package_info.name}", ""]
    lines.append(f"Total modules: {len(package_info.modules)}")
    lines.append(f"Total classes: {len(package_info.classes)}")
    lines.append(f"Total relations: {len(package_info.relations)}")
    lines.append("")

    if package_info.circular_dependencies:
        lines.append("## ⚠️ Dépendances circulaires détectées")
        lines.append("")
        for idx, cycle in enumerate(package_info.circular_dependencies, 1):
            lines.append(f"{idx}. {' -> '.join(cycle)}")
        lines.append("")

    lines.append("## Modules")
    for mod_name, mod_info in sorted(package_info.modules.items()):
        lines.append(f"- `{mod_name}` ({len(mod_info.classes)} classes, {len(mod_info.internal_imports)} imports internes)")

    lines.append("")
    lines.append("## Dépendances")
    for src, deps in sorted(package_info.dependencies.items()):
        if deps:
            lines.append(f"- `{src}` dépend de: {', '.join(f'`{d}`' for d in sorted(deps))}")

    return "\n".join(lines)
