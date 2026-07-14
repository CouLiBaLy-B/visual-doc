"""Générateur SVG simple (fallback si Graphviz/Mermaid CLI absent)."""

from __future__ import annotations

import html
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo, PackageInfo

from ..analyzer.models import RelationType


def _escape(text: str) -> str:
    return html.escape(text)


def generate_class_diagram_svg(
    classes: dict[str, "ClassInfo"],
    relations: list["RelationInfo"],
    width: int = 800,
    title: str | None = None,
) -> str:
    """Génère un SVG simple pour diagramme de classes."""

    sorted_classes = sorted(classes.values(), key=lambda c: c.name)
    n = len(sorted_classes)
    if n == 0:
        return _empty_svg("Aucune classe", width)

    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)

    box_w = 220
    box_h_min = 80
    # hauteur variable selon nb attrs/methods
    # pour simplifier: fixe
    box_h = 150
    gap_x = 40
    gap_y = 60

    total_w = cols * (box_w + gap_x) + gap_x
    total_h = rows * (box_h + gap_y) + gap_y + (40 if title else 0)
    total_w = max(total_w, width)

    # positions
    positions: dict[str, tuple[int, int]] = {}
    for idx, cls in enumerate(sorted_classes):
        col = idx % cols
        row = idx // cols
        x = gap_x + col * (box_w + gap_x)
        y = gap_y + row * (box_h + gap_y) + (40 if title else 0)
        positions[cls.name] = (x, y)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" viewBox="0 0 {total_w} {total_h}">',
        "<style>",
        ".class-box { fill: #ffffff; stroke: #333; stroke-width: 1.5; }",
        ".class-title { font: bold 14px sans-serif; fill: #111; }",
        ".class-sep { stroke: #333; stroke-width: 1; }",
        ".class-member { font: 11px monospace; fill: #333; }",
        ".relation { stroke: #333; stroke-width: 1.5; fill: none; }",
        ".inheritance { stroke: #333; stroke-width: 1.5; fill: white; }",
        ".label { font: 10px sans-serif; fill: #555; }",
        "</style>",
    ]

    if title:
        svg_parts.append(f'<text x="{total_w/2}" y="25" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold">{_escape(title)}</text>')

    # relations d'abord (arrière-plan)
    for rel in relations:
        src_name = rel.source.split(".")[-1]
        tgt_name = rel.target.split(".")[-1]
        if src_name not in positions or tgt_name not in positions:
            continue
        x1, y1 = positions[src_name]
        x2, y2 = positions[tgt_name]
        # centre des boites
        cx1 = x1 + box_w / 2
        cy1 = y1 + box_h / 2
        cx2 = x2 + box_w / 2
        cy2 = y2 + box_h / 2

        # ligne
        if rel.relation_type == RelationType.INHERITANCE:
            svg_parts.append(
                f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" class="relation" marker-end="url(#inheritance)"/>'
            )
        elif rel.relation_type == RelationType.COMPOSITION:
            svg_parts.append(
                f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" class="relation" marker-end="url(#composition)"/>'
            )
        else:
            svg_parts.append(f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" class="relation" stroke-dasharray="5,5"/>')

        # label
        if rel.label:
            mx = (cx1 + cx2) / 2
            my = (cy1 + cy2) / 2
            svg_parts.append(f'<text x="{mx}" y="{my}" class="label">{_escape(rel.label)}</text>')

    # Définir markers
    svg_parts.append("<defs>")
    svg_parts.append('<marker id="inheritance" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="white" stroke="#333"/></marker>')
    svg_parts.append('<marker id="composition" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 5 L 5 0 L 10 5 L 5 10 z" fill="#333"/></marker>')
    svg_parts.append("</defs>")

    # Boites classes
    for cls in sorted_classes:
        x, y = positions[cls.name]
        # calculer hauteur nécessaire
        attrs = cls.attributes[:5]
        methods = cls.methods[:6]
        needed_h = 25 + len(attrs) * 14 + (10 if attrs and methods else 0) + len(methods) * 14 + 10
        h = max(box_h, needed_h)

        svg_parts.append(f'<rect x="{x}" y="{y}" width="{box_w}" height="{h}" class="class-box" rx="4"/>')
        # titre
        svg_parts.append(f'<text x="{x+box_w/2}" y="{y+18}" text-anchor="middle" class="class-title">{_escape(cls.name)}</text>')
        svg_parts.append(f'<line x1="{x}" y1="{y+25}" x2="{x+box_w}" y2="{y+25}" class="class-sep"/>')

        cur_y = y + 40
        for attr in attrs:
            txt = attr.mermaid_str()[:30]
            svg_parts.append(f'<text x="{x+8}" y="{cur_y}" class="class-member">{_escape(txt)}</text>')
            cur_y += 14
        if attrs and methods:
            svg_parts.append(f'<line x1="{x}" y1="{cur_y-5}" x2="{x+box_w}" y2="{cur_y-5}" class="class-sep" stroke-dasharray="3,3"/>')
        for method in methods:
            txt = method.mermaid_signature()[:30]
            svg_parts.append(f'<text x="{x+8}" y="{cur_y}" class="class-member">{_escape(txt)}</text>')
            cur_y += 14

        # lien cliquable ? SVG cliquable: ajouter <a>
        # Pour rendre cliquable, on entoure de <a href="#{cls.name}"> ? placeholder
        # On va ajouter titre

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def generate_package_diagram_svg(package_info: "PackageInfo", width: int = 900) -> str:
    """Génère SVG pour dépendances packages."""

    modules = sorted(package_info.modules.keys())
    n = len(modules)
    if n == 0:
        return _empty_svg("Aucun module", width)

    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)
    box_w = 160
    box_h = 50
    gap_x = 60
    gap_y = 80
    total_w = cols * (box_w + gap_x) + gap_x
    total_h = rows * (box_h + gap_y) + gap_y + 40
    total_w = max(total_w, width)

    positions: dict[str, tuple[int, int]] = {}
    for idx, mod in enumerate(modules):
        col = idx % cols
        row = idx // cols
        x = gap_x + col * (box_w + gap_x)
        y = gap_y + row * (box_h + gap_y) + 20
        positions[mod] = (x, y)

    # cycles
    circular_nodes = set()
    circular_edges = set()
    for cycle in package_info.circular_dependencies:
        for i in range(len(cycle) - 1):
            circular_edges.add((cycle[i], cycle[i + 1]))
            circular_nodes.add(cycle[i])
            circular_nodes.add(cycle[i + 1])

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" viewBox="0 0 {total_w} {total_h}">',
        "<style>",
        ".mod-box { fill: #e3f2fd; stroke: #1976d2; stroke-width: 1.5; }",
        ".mod-box-circular { fill: #ffcccc; stroke: #ff0000; stroke-width: 2.5; }",
        ".mod-text { font: 12px sans-serif; fill: #111; }",
        ".dep-line { stroke: #555; stroke-width: 1.2; fill: none; }",
        ".dep-circular { stroke: #ff0000; stroke-width: 2; fill: none; }",
        "</style>",
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#555"/></marker>',
        '<marker id="arrow-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#ff0000"/></marker>',
        "</defs>",
    ]

    # dépendances lignes
    for src, deps in package_info.dependencies.items():
        if src not in positions:
            continue
        x1, y1 = positions[src]
        cx1 = x1 + box_w / 2
        cy1 = y1 + box_h / 2
        for tgt in deps:
            if tgt not in positions:
                continue
            x2, y2 = positions[tgt]
            cx2 = x2 + box_w / 2
            cy2 = y2 + box_h / 2
            is_circular = (src, tgt) in circular_edges or (tgt, src) in circular_edges
            cls = "dep-circular" if is_circular else "dep-line"
            marker = "url(#arrow-red)" if is_circular else "url(#arrow)"
            svg_parts.append(
                f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" class="{cls}" marker-end="{marker}"/>'
            )

    # boites
    for mod in modules:
        x, y = positions[mod]
        is_circ = mod in circular_nodes
        box_cls = "mod-box-circular" if is_circ else "mod-box"
        display = mod.split(".")[-1]
        full = mod
        # rendre cliquable: <a href>
        svg_parts.append(f'<a href="#{mod.replace(".", "-")}"><rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" class="{box_cls}" rx="6"/>')
        svg_parts.append(f'<text x="{x+box_w/2}" y="{y+20}" text-anchor="middle" class="mod-text" font-weight="bold">{_escape(display)}</text>')
        svg_parts.append(f'<text x="{x+box_w/2}" y="{y+35}" text-anchor="middle" class="mod-text" font-size="10">{_escape(full[:22])}</text>')
        svg_parts.append("</a>")

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _empty_svg(message: str, width: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="100"><text x="10" y="50">{_escape(message)}</text></svg>'


def save_svg(content: str, path) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def try_convert_svg_to_png(svg_path, png_path) -> bool:
    """Tente conversion SVG->PNG via cairosvg ou inkscape si dispo."""
    from pathlib import Path
    import shutil
    import subprocess

    svg_path = Path(svg_path)
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    # Essayer cairosvg
    try:
        import cairosvg

        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return True
    except Exception:
        pass

    # Essayer inkscape
    if shutil.which("inkscape"):
        try:
            subprocess.run(
                ["inkscape", str(svg_path), "--export-type=png", f"--export-filename={png_path}"],
                check=True,
                timeout=10,
            )
            return True
        except Exception:
            pass

    # Essayer rsvg-convert
    if shutil.which("rsvg-convert"):
        try:
            subprocess.run(
                ["rsvg-convert", str(svg_path), "-o", str(png_path)],
                check=True,
                timeout=10,
            )
            return True
        except Exception:
            pass

    return False
