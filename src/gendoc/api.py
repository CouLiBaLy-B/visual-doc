"""API publique pour utiliser gendoc comme librairie Python.

Cette API permet d'intégrer gendoc dans d'autres outils, scripts, ou notebooks.

Exemples:
    >>> import gendoc
    >>> pkg = gendoc.analyze_package("./mon_package")
    >>> print(f"{len(pkg.classes)} classes")
    >>> gendoc.build_docs("./mon_package", output_dir="./site")
    >>> # Ou usage avancé avec config
    >>> cfg = gendoc.GendocConfig(package_path="src/mon_pkg", public_only=True)
    >>> site_path = gendoc.build_docs_with_config(cfg)

Tout est 100% local, sans appel réseau.
"""

from __future__ import annotations

from pathlib import Path

from .analyzer import analyze_package, get_focused_subgraph
from .analyzer.models import PackageInfo
from .builder import SiteBuilder
from .config import GendocConfig
from .renderers import (
    generate_class_diagram_mermaid,
    generate_class_diagram_plantuml,
    generate_class_diagram_svg,
    generate_module_class_diagram_mermaid,
    generate_module_class_diagram_plantuml,
    generate_package_diagram_mermaid,
    generate_package_diagram_plantuml,
    generate_package_diagram_svg,
)


def analyze(
    package_path: str | Path,
    package_name: str | None = None,
    exclude_patterns: list[str] | None = None,
    include_private: bool = False,
    public_only: bool = False,
    include_tests: bool = False,
    strict: bool = False,
) -> PackageInfo:
    """Analyse un package et retourne les infos structurées.

    Args:
        package_path: Chemin vers le package.
        package_name: Nom du package (auto-détecté sinon).
        exclude_patterns: Patterns à exclure.
        include_private: Inclure classes/fonctions privées (préfixe `_`).
        public_only: Retirer les membres non publics des classes retournées.
        include_tests: Inclure les fichiers de tests.
        strict: Échouer si un fichier n'est pas parsable (sinon PackageInfo.errors).

    Returns:
        PackageInfo avec modules, classes, relations, dépendances circulaires.
    """
    pkg = analyze_package(
        root_path=Path(package_path),
        package_name=package_name,
        exclude_patterns=exclude_patterns,
        include_private=include_private,
        include_tests=include_tests,
        strict=strict,
    )
    if public_only:
        for cls in pkg.classes.values():
            cls.attributes = [a for a in cls.attributes if a.visibility.value == "public"]
            cls.methods = [m for m in cls.methods if m.visibility.value == "public"]
    return pkg


def build_docs(
    package_path: str | Path,
    output_dir: str | Path = "site",
    docs_dir: str | Path = "docs",
    formats: list[str] | None = None,
    public_only: bool = False,
    focus_class: str | None = None,
    focus_depth: int = 2,
    site_name: str = "Documentation",
) -> Path:
    """Génère documentation complète (API haut niveau).

    Args:
        package_path: Chemin package.
        output_dir: Dossier site HTML.
        docs_dir: Dossier markdown source.
        formats: ["mmd", "puml", "svg", "png"].
        public_only: Filtrer membres publics seuls.
        focus_class: Classe pour diagramme ciblé.
        focus_depth: Profondeur focus.
        site_name: Nom site MkDocs.

    Returns:
        Chemin vers dossier docs généré.

    Example:
        >>> import gendoc
        >>> gendoc.build_docs("./example/example_pkg", output_dir="./site")
    """
    cfg = GendocConfig(
        package_path=Path(package_path),
        output_dir=Path(output_dir),
        docs_dir=Path(docs_dir),
        formats=formats or ["mmd", "puml", "svg"],
        public_only=public_only,
        focus_class=focus_class,
        focus_depth=focus_depth,
        site_name=site_name,
    )
    return build_docs_with_config(cfg)


def build_docs_with_config(config: GendocConfig) -> Path:
    """Génère docs à partir d'une config existante.

    Args:
        config: GendocConfig.

    Returns:
        Path vers docs.
    """
    pkg_info = analyze_package(
        root_path=config.package_path,
        package_name=config.package_name,
        exclude_patterns=config.exclude_patterns,
        include_private=config.include_private,
        include_tests=config.include_tests,
    )
    builder = SiteBuilder(config, pkg_info)
    return builder.build()


def get_diagrams(
    package_path: str | Path | None = None,
    diagram_format: str = "mermaid",
    focus_class: str | None = None,
    depth: int = 2,
    package_info: PackageInfo | None = None,
) -> dict[str, str]:
    """Retourne les diagrammes sous forme de strings (lib usage).

    Args:
        package_path: Chemin package (ignoré si package_info est fourni).
        diagram_format: "mermaid" ou "plantuml" ou "svg".
        focus_class: Si défini, retourne sous-graphe centré.
        depth: Profondeur pour focus.
        package_info: Résultat d'une analyse déjà faite, pour éviter de ré-analyser.

    Returns:
        Dict {nom: contenu diagramme}.

    Example:
        >>> import gendoc
        >>> diags = gendoc.get_diagrams("./example/example_pkg", "mermaid")
        >>> print(diags["package"])
        >>> print(diags["classes"])
    """
    if package_info is not None:
        pkg = package_info
    else:
        if package_path is None:
            raise ValueError("package_path ou package_info est requis")
        pkg = analyze_package(Path(package_path))

    result: dict[str, str] = {}

    # Package diagram
    if diagram_format == "mermaid":
        result["package"] = generate_package_diagram_mermaid(pkg)
        result["classes"] = generate_class_diagram_mermaid(pkg.classes, pkg.relations)
    elif diagram_format == "plantuml":
        result["package"] = generate_package_diagram_plantuml(pkg)
        result["classes"] = generate_class_diagram_plantuml(pkg.classes, pkg.relations)
    elif diagram_format == "svg":
        result["package"] = generate_package_diagram_svg(pkg)
        result["classes"] = generate_class_diagram_svg(pkg.classes, pkg.relations)
    else:
        raise ValueError(f"Format inconnu: {diagram_format}, attendu mermaid|plantuml|svg")

    # Focus si demandé
    if focus_class:
        focused_classes, focused_rels = get_focused_subgraph(
            pkg.classes, pkg.relations, focus_class, depth
        )
        if diagram_format == "mermaid":
            result[f"focus_{focus_class}"] = generate_class_diagram_mermaid(
                focused_classes, focused_rels, title=f"Focus {focus_class}"
            )
        elif diagram_format == "plantuml":
            result[f"focus_{focus_class}"] = generate_class_diagram_plantuml(
                focused_classes, focused_rels, title=f"Focus {focus_class}"
            )
        else:
            result[f"focus_{focus_class}"] = generate_class_diagram_svg(
                focused_classes, focused_rels, title=f"Focus {focus_class}"
            )

    # Par module
    for dotted, mod in pkg.modules.items():
        safe = dotted.replace(".", "_")
        if diagram_format == "mermaid":
            result[f"module_{safe}"] = generate_module_class_diagram_mermaid(
                dotted, mod.classes, pkg.relations
            )
        elif diagram_format == "plantuml":
            result[f"module_{safe}"] = generate_module_class_diagram_plantuml(
                dotted, mod.classes, pkg.relations
            )
        else:
            class_map = {c.qualified_name: c for c in mod.classes}
            result[f"module_{safe}"] = generate_class_diagram_svg(class_map, [])

    return result


def check_package(package_path: str | Path) -> bool:
    """Vérifie si package analysable (pour CI ou lib).

    Returns:
        True si analysable, False sinon (ou lève exception si verbose).

    Example:
        >>> import gendoc
        >>> gendoc.check_package("./mon_package")
        True
    """
    try:
        analyze_package(Path(package_path))
        return True
    except Exception:
        return False


# API legacy / pratique pour notebooks
def quick_overview(package_path: str | Path) -> str:
    """Retourne résumé texte rapide pour affichage.

    Example:
        >>> print(gendoc.quick_overview("./example/example_pkg"))
    """
    pkg = analyze_package(Path(package_path))
    lines = [
        f"Package: {pkg.name}",
        f"Modules: {len(pkg.modules)}",
        f"Classes: {len(pkg.classes)}",
        f"Relations: {len(pkg.relations)}",
        f"Circular deps: {len(pkg.circular_dependencies)}",
    ]
    if pkg.circular_dependencies:
        from .analyzer.relationships import cycle_display

        lines.append("Cycles:")
        for cycle in pkg.circular_dependencies:
            lines.append(f"  - {cycle_display(cycle)}")
    lines.append("\nModules:")
    for mod in sorted(pkg.modules.keys()):
        lines.append(f"  - {mod} ({len(pkg.modules[mod].classes)} classes)")
    return "\n".join(lines)
