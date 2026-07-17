"""Générateur SVG simple (fallback si Graphviz/Mermaid CLI absent)."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, PackageInfo, RelationInfo

from ..analyzer.models import RelationType
from .common import attribute_plain, circular_edge_set, method_plain, sorted_package_edges
from .common import escape_svg_text as _escape

logger = logging.getLogger(__name__)


def _truncate(text: str, limit: int = 30) -> str:
    """Tronque avec une ellipse visible plutôt que silencieusement."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def generate_class_diagram_svg(
    classes: dict[str, ClassInfo],
    relations: list[RelationInfo],
    width: int = 800,
    title: str | None = None,
) -> str:
    """Génère un SVG simple pour diagramme de classes.

    Les positions sont indexées par nom qualifié : deux classes homonymes de
    modules différents occupent des boîtes distinctes.
    """
    sorted_classes = sorted(classes.values(), key=lambda c: c.qualified_name)
    n = len(sorted_classes)
    if n == 0:
        return _empty_svg("Aucune classe", width)

    cols = max(1, math.ceil(math.sqrt(n)))
    rows = math.ceil(n / cols)

    box_w = 220
    min_box_h = 80
    gap_x = 40
    gap_y = 60
    max_attrs = 5
    max_methods = 6

    def needed_height(cls: ClassInfo) -> int:
        attrs = cls.attributes[:max_attrs]
        methods = cls.methods[:max_methods]
        needed = 25 + len(attrs) * 14 + (10 if attrs and methods else 0) + len(methods) * 14 + 10
        return max(min_box_h, needed)

    heights = {c.qualified_name: needed_height(c) for c in sorted_classes}

    # hauteur de chaque rangée = la plus haute boîte de la rangée (pas de chevauchement)
    title_offset = 40 if title else 0
    row_tops: list[int] = []
    y_cursor = gap_y + title_offset
    for r in range(rows):
        row_classes = sorted_classes[r * cols : (r + 1) * cols]
        row_tops.append(y_cursor)
        y_cursor += max(heights[c.qualified_name] for c in row_classes) + gap_y

    total_w = max(cols * (box_w + gap_x) + gap_x, width)
    total_h = y_cursor

    positions: dict[str, tuple[int, int]] = {}
    for idx, cls in enumerate(sorted_classes):
        col = idx % cols
        row = idx // cols
        x = gap_x + col * (box_w + gap_x)
        positions[cls.qualified_name] = (x, row_tops[row])

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">',
        "<style>",
        ".class-box { fill: #ffffff; stroke: #333; stroke-width: 1.5; }",
        ".class-title { font: bold 14px sans-serif; fill: #111; }",
        ".class-sep { stroke: #333; stroke-width: 1; }",
        ".class-member { font: 11px monospace; fill: #333; }",
        ".relation { stroke: #333; stroke-width: 1.5; fill: none; }",
        ".inheritance { stroke: #333; stroke-width: 1.5; fill: white; }",
        ".label { font: 10px sans-serif; fill: #555; }",
        "</style>",
        "<defs>",
        '<marker id="inheritance" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="white" stroke="#333"/></marker>',
        '<marker id="composition" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="8" '
        'markerHeight="8" orient="auto-start-reverse">'
        '<path d="M 0 5 L 5 0 L 10 5 L 5 10 z" fill="#333"/></marker>',
        "</defs>",
    ]

    if title:
        svg_parts.append(
            f'<text x="{total_w / 2}" y="25" text-anchor="middle" font-family="sans-serif" '
            f'font-size="16" font-weight="bold">{_escape(title)}</text>'
        )

    # relations d'abord (arrière-plan)
    for rel in relations:
        if rel.source not in positions or rel.target not in positions:
            continue
        x1, y1 = positions[rel.source]
        x2, y2 = positions[rel.target]
        cx1 = x1 + box_w / 2
        cy1 = y1 + heights[rel.source] / 2
        cx2 = x2 + box_w / 2
        cy2 = y2 + heights[rel.target] / 2

        line_pos = f'x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}"'
        if rel.relation_type == RelationType.INHERITANCE:
            svg_parts.append(f'<line {line_pos} class="relation" marker-end="url(#inheritance)"/>')
        elif rel.relation_type == RelationType.COMPOSITION:
            svg_parts.append(f'<line {line_pos} class="relation" marker-end="url(#composition)"/>')
        else:
            svg_parts.append(f'<line {line_pos} class="relation" stroke-dasharray="5,5"/>')

        if rel.label:
            mx = (cx1 + cx2) / 2
            my = (cy1 + cy2) / 2
            svg_parts.append(f'<text x="{mx}" y="{my}" class="label">{_escape(rel.label)}</text>')

    # Boîtes classes
    for cls in sorted_classes:
        x, y = positions[cls.qualified_name]
        h = heights[cls.qualified_name]
        attrs = cls.attributes[:max_attrs]
        methods = cls.methods[:max_methods]

        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{h}" class="class-box" rx="4"/>'
        )
        svg_parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 18}" text-anchor="middle" class="class-title">'
            f"{_escape(_truncate(cls.name, 26))}</text>"
        )
        svg_parts.append(
            f'<line x1="{x}" y1="{y + 25}" x2="{x + box_w}" y2="{y + 25}" class="class-sep"/>'
        )

        cur_y = y + 40
        for attr in attrs:
            txt = _truncate(attribute_plain(attr))
            svg_parts.append(
                f'<text x="{x + 8}" y="{cur_y}" class="class-member">{_escape(txt)}</text>'
            )
            cur_y += 14
        if attrs and methods:
            svg_parts.append(
                f'<line x1="{x}" y1="{cur_y - 5}" x2="{x + box_w}" y2="{cur_y - 5}" '
                'class="class-sep" stroke-dasharray="3,3"/>'
            )
        for method in methods:
            txt = _truncate(method_plain(method))
            svg_parts.append(
                f'<text x="{x + 8}" y="{cur_y}" class="class-member">{_escape(txt)}</text>'
            )
            cur_y += 14
        hidden = max(0, len(cls.attributes) - max_attrs) + max(0, len(cls.methods) - max_methods)
        if hidden:
            svg_parts.append(
                f'<text x="{x + 8}" y="{cur_y}" class="class-member">… (+{hidden} membres)</text>'
            )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def generate_package_diagram_svg(package_info: PackageInfo, width: int = 900) -> str:
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

    # cycles : arêtes orientées, y compris celle qui referme la boucle
    circular_nodes, circular_edges = circular_edge_set(package_info.circular_dependencies)

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
        f'viewBox="0 0 {total_w} {total_h}">',
        "<style>",
        ".mod-box { fill: #e3f2fd; stroke: #1976d2; stroke-width: 1.5; }",
        ".mod-box-circular { fill: #ffcccc; stroke: #ff0000; stroke-width: 2.5; }",
        ".mod-text { font: 12px sans-serif; fill: #111; }",
        ".dep-line { stroke: #555; stroke-width: 1.2; fill: none; }",
        ".dep-circular { stroke: #ff0000; stroke-width: 2; fill: none; }",
        "</style>",
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#555"/></marker>',
        '<marker id="arrow-red" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
        'markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#ff0000"/></marker>',
        "</defs>",
    ]

    # dépendances (arêtes partagées, ordre déterministe)
    for src, tgt in sorted_package_edges(package_info):
        if src not in positions or tgt not in positions:
            continue
        x1, y1 = positions[src]
        x2, y2 = positions[tgt]
        cx1 = x1 + box_w / 2
        cy1 = y1 + box_h / 2
        cx2 = x2 + box_w / 2
        cy2 = y2 + box_h / 2
        is_circular = (src, tgt) in circular_edges
        cls = "dep-circular" if is_circular else "dep-line"
        marker = "url(#arrow-red)" if is_circular else "url(#arrow)"
        svg_parts.append(
            f'<line x1="{cx1}" y1="{cy1}" x2="{cx2}" y2="{cy2}" '
            f'class="{cls}" marker-end="{marker}"/>'
        )

    # boîtes
    for mod in modules:
        x, y = positions[mod]
        box_cls = "mod-box-circular" if mod in circular_nodes else "mod-box"
        display = mod.split(".")[-1]
        svg_parts.append(
            f'<rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" class="{box_cls}" rx="6"/>'
        )
        svg_parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 20}" text-anchor="middle" class="mod-text" '
            f'font-weight="bold">{_escape(display)}</text>'
        )
        svg_parts.append(
            f'<text x="{x + box_w / 2}" y="{y + 35}" text-anchor="middle" class="mod-text" '
            f'font-size="10">{_escape(_truncate(mod, 24))}</text>'
        )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def _empty_svg(message: str, width: int) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="100">'
        f'<text x="10" y="50">{_escape(message)}</text></svg>'
    )


def save_svg(content: str, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def try_convert_svg_to_png(svg_path: str | Path, png_path: str | Path) -> bool:
    """Tente conversion SVG->PNG via cairosvg, inkscape ou rsvg-convert si dispo."""
    import shutil
    import subprocess

    svg_path = Path(svg_path)
    png_path = Path(png_path)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cairosvg

        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path))
        return True
    except ImportError:
        logger.debug("cairosvg absent, conversion PNG via outils externes")
    except Exception as e:
        import warnings

        warnings.warn(
            f"Conversion cairosvg échouée pour {svg_path}: {e}", RuntimeWarning, stacklevel=2
        )

    if shutil.which("inkscape"):
        try:
            subprocess.run(
                ["inkscape", str(svg_path), "--export-type=png", f"--export-filename={png_path}"],
                check=True,
                timeout=10,
            )
            return True
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("conversion inkscape échouée pour %s: %s", svg_path, e)

    if shutil.which("rsvg-convert"):
        try:
            subprocess.run(
                ["rsvg-convert", str(svg_path), "-o", str(png_path)],
                check=True,
                timeout=10,
            )
            return True
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug("conversion rsvg-convert échouée pour %s: %s", svg_path, e)

    return False
