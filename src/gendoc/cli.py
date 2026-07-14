"""CLI gendoc."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .config import GendocConfig, load_config
from .analyzer import analyze_package
from .builder import SiteBuilder

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="gendoc")
def cli() -> None:
    """gendoc - Pipeline de documentation graphique automatique."""
    pass


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path), default=Path("."))
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Chemin vers gendoc.toml")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Dossier de sortie (site)")
@click.option("--exclude", multiple=True, help="Pattern à exclure (peut être répété)")
@click.option("--include-private", is_flag=True, help="Inclure fichiers/membres privés")
@click.option("--public-only", is_flag=True, help="Filtrer uniquement membres publics")
@click.option("--formats", help="Formats de sortie séparés par virgule (mmd,puml,svg,png)")
@click.option("--focus", help="Classe focus pour diagramme ciblé")
@click.option("--depth", type=int, default=None, help="Profondeur pour focus (défaut 2)")
@click.option("--site-name", help="Nom du site")
@click.option("--build-site/--no-build-site", default=True, help="Construire site MkDocs HTML après génération")
@click.option("--verbose", "-v", is_flag=True, help="Mode verbeux")
def build(
    package_path: Path,
    config: Optional[Path],
    output: Optional[Path],
    exclude: tuple[str, ...],
    include_private: bool,
    public_only: bool,
    formats: Optional[str],
    focus: Optional[str],
    depth: Optional[int],
    site_name: Optional[str],
    build_site: bool,
    verbose: bool,
) -> None:
    """Génère documentation visuelle pour un package Python.

    PACKAGE_PATH: chemin vers le package à documenter (défaut: .)
    """

    start = time.time()

    # Charger config
    cfg = load_config(config_path=config, package_path=package_path)

    # Override CLI
    fmt_list = None
    if formats:
        fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    cfg.merge_cli(
        package_path=package_path,
        output_dir=output,
        exclude=list(exclude) if exclude else None,
        include_private=True if include_private else None,
        public_only=True if public_only else None,
        formats=fmt_list,
        focus_class=focus,
        focus_depth=depth,
        site_name=site_name,
    )

    # Si include_private flag présent, c'est True sinon on garde config
    # Pour CLI, --include-private set True; si non présent, on ne touche pas. On a déjà logique.
    # De même pour public_only
    # Pour gérer explicitement false, on garde simple: flags bool => si flag non présent, None, on a déjà mis True seulement si présent
    # Donc réajuster include_private si utilisateur n'a pas mis flag
    if not include_private:
        # on ne peut distinguer false vs non présent; on laisse config telle quelle
        # on a passé None si false, donc config garde valeur toml
        pass

    console.print(f"[bold blue]gendoc[/] - Analyse de [cyan]{cfg.package_path}[/]")

    # Vérifier package_path analysable?
    if not cfg.package_path.exists():
        console.print(f"[red]Erreur: chemin {cfg.package_path} introuvable[/]")
        sys.exit(1)

    # Afficher config si verbose
    if verbose:
        console.print(f"[dim]Config: package_name={cfg.package_name}, output={cfg.output_dir}, formats={cfg.formats}")
        console.print(f"[dim]Exclude: {cfg.exclude_patterns}, include_private={cfg.include_private}, public_only={cfg.public_only}")

    # Analyse
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Analyse du package...", total=None)
        try:
            package_info = analyze_package(
                root_path=cfg.package_path,
                package_name=cfg.package_name,
                exclude_patterns=cfg.exclude_patterns,
                include_private=cfg.include_private,
                include_tests=cfg.include_tests,
            )
            progress.update(task, description=f"Analyse terminée: {len(package_info.modules)} modules, {len(package_info.classes)} classes")
            time.sleep(0.3)
        except RuntimeError as e:
            console.print(f"[red]Échec analyse: {e}[/]")
            sys.exit(2)
        except Exception as e:
            console.print(f"[red]Erreur inattendue lors de l'analyse: {e}[/]")
            if verbose:
                console.print_exception()
            sys.exit(2)

    # Résumé
    table = Table(title="Résumé analyse")
    table.add_column("Métrique", style="cyan")
    table.add_column("Valeur", style="magenta")
    table.add_row("Modules", str(len(package_info.modules)))
    table.add_row("Classes", str(len(package_info.classes)))
    table.add_row("Relations", str(len(package_info.relations)))
    table.add_row("Dépendances circulaires", str(len(package_info.circular_dependencies)))
    if package_info.circular_dependencies:
        for idx, cycle in enumerate(package_info.circular_dependencies[:3], 1):
            table.add_row(f"Cycle {idx}", " -> ".join(cycle))
    console.print(table)

    if not package_info.modules:
        console.print("[yellow]Aucun module trouvé, vérifiez le chemin[/]")
        sys.exit(1)

    # Génération site
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Génération documentation...", total=None)
        try:
            builder = SiteBuilder(cfg, package_info)
            docs_path = builder.build()
            progress.update(task, description=f"Docs générées dans {docs_path}")
        except Exception as e:
            console.print(f"[red]Erreur génération site: {e}[/]")
            if verbose:
                console.print_exception()
            sys.exit(3)

    # Build MkDocs site HTML si demandé
    if build_site:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Construction site MkDocs...", total=None)
            try:
                import subprocess
                import os

                # Trouver mkdocs.yml
                mkdocs_yml = docs_path.parent / "mkdocs.yml"
                if not mkdocs_yml.exists():
                    mkdocs_yml = Path.cwd() / "mkdocs.yml"

                if mkdocs_yml.exists():
                    output_site = cfg.output_dir
                    if not output_site.is_absolute():
                        output_site = (Path.cwd() / output_site).resolve()
                    output_site.mkdir(parents=True, exist_ok=True)

                    # Préparer PYTHONPATH pour mkdocstrings
                    env = os.environ.copy()
                    # Ajouter cwd, parent du package, root_path, src
                    paths_to_add = []
                    cwd = Path.cwd()
                    paths_to_add.append(str(cwd))
                    # package root parent
                    try:
                        pkg_root = package_info.root_path.resolve()
                        pkg_parent = pkg_root.parent.resolve()
                        paths_to_add.append(str(pkg_parent))
                        paths_to_add.append(str(pkg_root))
                        # Si package est example/example_pkg, parent = example, déjà ajouté
                        # Mais aussi parent du parent (project root)
                        paths_to_add.append(str(pkg_parent.parent.resolve()))
                    except Exception:
                        pass
                    src_path = cwd / "src"
                    if src_path.exists():
                        paths_to_add.append(str(src_path.resolve()))
                    example_path = cwd / "example"
                    if example_path.exists():
                        paths_to_add.append(str(example_path.resolve()))

                    # Dédoublonner et construire PYTHONPATH
                    seen = set()
                    uniq_paths = []
                    for p in paths_to_add:
                        if p not in seen:
                            seen.add(p)
                            uniq_paths.append(p)
                    # Ajouter au PYTHONPATH existant
                    existing_pp = env.get("PYTHONPATH", "")
                    new_pp = ":".join(uniq_paths)
                    if existing_pp:
                        new_pp = new_pp + ":" + existing_pp
                    env["PYTHONPATH"] = new_pp

                    if verbose:
                        console.print(f"[dim]PYTHONPATH pour mkdocs: {new_pp}")

                    # lancer mkdocs build
                    result = subprocess.run(
                        ["mkdocs", "build", "-f", str(mkdocs_yml), "-d", str(output_site)],
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    if result.returncode != 0:
                        # Afficher stderr mais ne pas échouer si warning mkdocstrings
                        # Si le site a quand même été généré partiellement, on garde
                        if verbose or "BuildError" in result.stderr or "ERROR" in result.stderr:
                            console.print(f"[yellow]MkDocs build warning: {result.stderr[-2000:]}[/]")
                            console.print(f"[dim]Stdout: {result.stdout[-1000:]}[/]")
                        # Vérifier si index.html existe quand même
                        if (output_site / "index.html").exists():
                            progress.update(task, description=f"Site HTML généré (avec warnings) dans {output_site}")
                        else:
                            # Si échec total, tenter build sans mkdocstrings strict?
                            # On laisse site markdown déjà généré
                            console.print(f"[yellow]Site HTML non généré, mais docs markdown OK dans {docs_path}[/]")
                    else:
                        progress.update(task, description=f"Site HTML généré dans {output_site}")
                else:
                    console.print(f"[yellow]mkdocs.yml non trouvé, génération markdown seulement dans {docs_path}[/]")
            except FileNotFoundError:
                console.print("[yellow]mkdocs non installé, génération markdown seulement[/]")
            except Exception as e:
                console.print(f"[yellow]Erreur build MkDocs: {e}[/]")
                if verbose:
                    console.print_exception()

    elapsed = time.time() - start
    console.print(f"[bold green]✓ Documentation générée en {elapsed:.2f}s[/]")

    # Vérification critères acceptance
    docs_path = Path.cwd() / "docs" if (Path.cwd() / "docs").exists() else cfg.output_dir.parent / "docs"
    # Chercher diagrams
    has_package_diagram = any((Path.cwd() / "docs" / "diagrams" / f).exists() for f in ["package.mmd", "package.svg"])
    # compter diagrammes modules
    mod_diagrams = list((Path.cwd() / "docs" / "diagrams").glob("*.mmd")) if (Path.cwd() / "docs" / "diagrams").exists() else []

    console.print(f"[dim]Vérif: package diagram ok={has_package_diagram}, modules diagrams={len(mod_diagrams)}")

    if elapsed > 60:
        console.print("[yellow]Warning: génération >60s (critère performance)[/]")

    # Succès
    site_dir = cfg.output_dir if cfg.output_dir.is_absolute() else (Path.cwd() / cfg.output_dir)
    console.print(f"\n[bold]Site disponible:[/] {site_dir / 'index.html'} (si build) ou [cyan]{docs_path}[/]")
    console.print("[bold]Commande pour servir:[/] mkdocs serve")


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path), default=Path("."))
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), default=Path("diagrams"))
@click.option("--format", "fmt", type=click.Choice(["mermaid", "plantuml", "svg", "all"]), default="all")
def diagram(package_path: Path, config: Optional[Path], output: Path, fmt: str) -> None:
    """Génère uniquement les diagrammes (sans site)."""

    cfg = load_config(config_path=config, package_path=package_path)
    cfg.merge_cli(package_path=package_path)

    console.print(f"Génération diagrammes pour {package_path} -> {output}")

    package_info = analyze_package(
        root_path=cfg.package_path,
        package_name=cfg.package_name,
        exclude_patterns=cfg.exclude_patterns,
        include_private=cfg.include_private,
        include_tests=cfg.include_tests,
    )

    output.mkdir(parents=True, exist_ok=True)

    from gendoc.renderers import (
        generate_class_diagram_mermaid,
        generate_class_diagram_plantuml,
        generate_class_diagram_svg,
        generate_package_diagram_mermaid,
        generate_package_diagram_plantuml,
        generate_package_diagram_svg,
        save_svg,
    )

    # Package
    if fmt in ("mermaid", "all"):
        (output / "package.mmd").write_text(generate_package_diagram_mermaid(package_info), encoding="utf-8")
    if fmt in ("plantuml", "all"):
        (output / "package.puml").write_text(generate_package_diagram_plantuml(package_info), encoding="utf-8")
    if fmt in ("svg", "all"):
        save_svg(generate_package_diagram_svg(package_info), output / "package.svg")

    # Global class
    if fmt in ("mermaid", "all"):
        (output / "classes.mmd").write_text(
            generate_class_diagram_mermaid(package_info.classes, package_info.relations), encoding="utf-8"
        )
    if fmt in ("plantuml", "all"):
        (output / "classes.puml").write_text(
            generate_class_diagram_plantuml(package_info.classes, package_info.relations), encoding="utf-8"
        )
    if fmt in ("svg", "all"):
        save_svg(
            generate_class_diagram_svg(package_info.classes, package_info.relations, title="Classes"),
            output / "classes.svg",
        )

    console.print(f"[green]Diagrammes générés dans {output}[/]")


@cli.command()
@click.argument("package_path", type=click.Path(exists=True, path_type=Path), default=Path("."))
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path))
def check(package_path: Path, config: Optional[Path]) -> None:
    """Vérifie si le code est analysable (pour CI)."""

    cfg = load_config(config_path=config, package_path=package_path)
    cfg.merge_cli(package_path=package_path)

    try:
        package_info = analyze_package(
            root_path=cfg.package_path,
            package_name=cfg.package_name,
            exclude_patterns=cfg.exclude_patterns,
            include_private=cfg.include_private,
            include_tests=cfg.include_tests,
        )
        console.print(f"[green]✓ Code analysable: {len(package_info.modules)} modules, {len(package_info.classes)} classes[/]")
        if package_info.circular_dependencies:
            console.print(f"[yellow]⚠ {len(package_info.circular_dependencies)} dépendance(s) circulaire(s) détectée(s)[/]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]✗ Code non analysable: {e}[/]")
        sys.exit(1)


@cli.command()
def init() -> None:
    """Initialise un fichier gendoc.toml exemple."""

    example_content = """# gendoc.toml - Configuration exemple

[gendoc]
# Chemin vers le package à documenter
package_path = "."
package_name = "mon_package"

# Sortie
output_dir = "site"
docs_dir = "docs"
formats = ["mmd", "puml", "svg", "png"]

# Filtrage
exclude_patterns = ["test_*", "*_test.py", "tests", "__pycache__", "build"]
include_private = false
include_tests = false
public_only = false
inheritance_depth = 3

# Diagramme ciblé (optionnel)
# focus_class = "MaClasse"
# focus_depth = 2

# Site
site_name = "Ma Documentation"
theme = "material"
enable_mermaid = true
repo_url = "https://github.com/username/repo"
"""

    target = Path("gendoc.toml")
    if target.exists():
        console.print(f"[yellow]{target} existe déjà[/]")
        if not click.confirm("Écraser ?"):
            return

    target.write_text(example_content, encoding="utf-8")
    console.print(f"[green]Fichier {target} créé[/]")


def main() -> None:
    cli()
