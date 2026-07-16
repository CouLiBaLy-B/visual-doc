"""CLI gendoc."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import __version__
from .analyzer import analyze_package
from .builder import SiteBuilder
from .config import load_config

console = Console()


def _mkdocs_env(package_info) -> dict[str, str]:
    """Environnement pour mkdocs : PYTHONPATH permettant à mkdocstrings d'importer le package."""
    import os

    paths = [str(Path.cwd())]
    try:
        pkg_root = package_info.root_path.resolve()
        paths.append(str(pkg_root.parent))
        paths.append(str(pkg_root))
        paths.append(str(pkg_root.parent.parent))
    except Exception:
        pass
    src_path = Path.cwd() / "src"
    if src_path.exists():
        paths.append(str(src_path.resolve()))

    env = os.environ.copy()
    unique_paths = list(dict.fromkeys(paths))
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(unique_paths) + (
        os.pathsep + existing if existing else ""
    )
    return env


@click.group()
@click.version_option(version=__version__, prog_name="gendoc")
def cli() -> None:
    """gendoc - Pipeline de documentation graphique automatique."""
    pass


@cli.command()
@click.argument(
    "package_path", type=click.Path(exists=True, path_type=Path), required=False, default=None
)
@click.option(
    "--config", "-c", type=click.Path(exists=True, path_type=Path), help="Chemin vers gendoc.toml"
)
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Dossier de sortie (site)")
@click.option("--exclude", multiple=True, help="Pattern à exclure (peut être répété)")
@click.option(
    "--include-private/--no-include-private",
    default=None,
    help="Inclure les éléments privés (surcharge le TOML dans les deux sens)",
)
@click.option(
    "--public-only/--no-public-only",
    default=None,
    help="Ne montrer que les membres publics (surcharge le TOML dans les deux sens)",
)
@click.option("--formats", help="Formats de sortie séparés par virgule (mmd,puml,svg,png)")
@click.option("--focus", help="Classe focus pour diagramme ciblé")
@click.option(
    "--depth", type=int, default=None, help="Profondeur pour focus (défaut: config, sinon 2)"
)
@click.option("--site-name", help="Nom du site")
@click.option(
    "--build-site/--no-build-site",
    default=True,
    help="Construire site MkDocs HTML après génération",
)
@click.option("--verbose", "-v", is_flag=True, help="Mode verbeux")
def build(
    package_path: Path | None,
    config: Path | None,
    output: Path | None,
    exclude: tuple[str, ...],
    include_private: bool | None,
    public_only: bool | None,
    formats: str | None,
    focus: str | None,
    depth: int | None,
    site_name: str | None,
    build_site: bool,
    verbose: bool,
) -> None:
    """Génère documentation visuelle pour un package Python.

    PACKAGE_PATH: chemin vers le package à documenter
    (défaut: package_path du gendoc.toml, sinon le répertoire courant)
    """

    start = time.time()

    # Charger config (l'argument CLI, s'il est fourni, prime sur le TOML)
    cfg = load_config(config_path=config, package_path=package_path)

    # Override CLI
    fmt_list = None
    if formats:
        fmt_list = [f.strip() for f in formats.split(",") if f.strip()]

    cfg.merge_cli(
        package_path=package_path,
        output_dir=output,
        exclude=list(exclude) if exclude else None,
        include_private=include_private,
        public_only=public_only,
        formats=fmt_list,
        focus_class=focus,
        focus_depth=depth,
        site_name=site_name,
    )

    console.print(f"[bold blue]gendoc[/] - Analyse de [cyan]{cfg.package_path}[/]")

    # Vérifier package_path analysable?
    if not cfg.package_path.exists():
        console.print(f"[red]Erreur: chemin {cfg.package_path} introuvable[/]")
        sys.exit(1)

    # Afficher config si verbose
    if verbose:
        console.print(
            f"[dim]Config: package_name={cfg.package_name}, "
            f"output={cfg.output_dir}, formats={cfg.formats}"
        )
        console.print(
            f"[dim]Exclude: {cfg.exclude_patterns}, "
            f"include_private={cfg.include_private}, public_only={cfg.public_only}"
        )

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
            progress.update(
                task,
                description=(
                    f"Analyse terminée: {len(package_info.modules)} modules, "
                    f"{len(package_info.classes)} classes"
                ),
            )
        except RuntimeError as e:
            console.print(f"[red]Échec analyse: {e}[/]")
            sys.exit(2)
        except Exception as e:
            console.print(f"[red]Erreur inattendue lors de l'analyse: {e}[/]")
            if verbose:
                console.print_exception()
            sys.exit(2)

    if package_info.errors:
        console.print(f"[yellow]⚠ {len(package_info.errors)} fichier(s) non parsables ignorés:[/]")
        for err in package_info.errors:
            console.print(f"  [yellow]- {err}[/]")

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
                import importlib.util
                import subprocess

                if importlib.util.find_spec("mkdocs") is None:
                    raise FileNotFoundError("module mkdocs absent")

                # Trouver mkdocs.yml
                mkdocs_yml = docs_path.parent / "mkdocs.yml"
                if not mkdocs_yml.exists():
                    mkdocs_yml = Path.cwd() / "mkdocs.yml"

                if mkdocs_yml.exists():
                    output_site = cfg.output_dir
                    if not output_site.is_absolute():
                        output_site = (Path.cwd() / output_site).resolve()
                    output_site.mkdir(parents=True, exist_ok=True)

                    env = _mkdocs_env(package_info)

                    if verbose:
                        console.print(f"[dim]PYTHONPATH pour mkdocs: {env['PYTHONPATH']}")

                    # lancer mkdocs build via l'interpréteur courant :
                    # fonctionne même si le bin/ du venv n'est pas sur le PATH
                    result = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "mkdocs",
                            "build",
                            "-f",
                            str(mkdocs_yml),
                            "-d",
                            str(output_site),
                        ],
                        capture_output=True,
                        text=True,
                        env=env,
                    )
                    if result.returncode != 0:
                        # Afficher stderr mais ne pas échouer si warning mkdocstrings
                        # Si le site a quand même été généré partiellement, on garde
                        if verbose or "BuildError" in result.stderr or "ERROR" in result.stderr:
                            console.print(
                                f"[yellow]MkDocs build warning: {result.stderr[-2000:]}[/]"
                            )
                            console.print(f"[dim]Stdout: {result.stdout[-1000:]}[/]")
                        # Vérifier si index.html existe quand même
                        if (output_site / "index.html").exists():
                            progress.update(
                                task,
                                description=f"Site HTML généré (avec warnings) dans {output_site}",
                            )
                        else:
                            console.print(
                                f"[yellow]Site HTML non généré, "
                                f"mais docs markdown OK dans {docs_path}[/]"
                            )
                    else:
                        progress.update(task, description=f"Site HTML généré dans {output_site}")
                else:
                    console.print(
                        f"[yellow]mkdocs.yml non trouvé, "
                        f"génération markdown seulement dans {docs_path}[/]"
                    )
            except FileNotFoundError:
                # le crochet est échappé pour ne pas être interprété comme balise Rich
                console.print(
                    "[yellow]mkdocs non installé (pip install 'gendoc\\[site]'), "
                    "génération markdown seulement[/]"
                )
            except Exception as e:
                console.print(f"[yellow]Erreur build MkDocs: {e}[/]")
                if verbose:
                    console.print_exception()

    elapsed = time.time() - start
    console.print(f"[bold green]✓ Documentation générée en {elapsed:.2f}s[/]")

    # Résumé des artefacts réellement générés (docs_path vient du builder)
    diag_dir = docs_path / "diagrams"
    mod_diagrams = sorted(diag_dir.glob("*.mmd")) if diag_dir.exists() else []
    console.print(
        f"[dim]Vérif: package diagram ok={(diag_dir / 'package.mmd').exists()}, "
        f"modules diagrams={len(mod_diagrams)}"
    )

    if elapsed > 60:
        console.print("[yellow]Warning: génération >60s (critère performance)[/]")

    # Succès
    site_dir = cfg.output_dir if cfg.output_dir.is_absolute() else (Path.cwd() / cfg.output_dir)
    console.print(
        f"\n[bold]Site disponible:[/] {site_dir / 'index.html'} (si build) ou [cyan]{docs_path}[/]"
    )
    console.print("[bold]Commande pour servir:[/] gendoc serve")


@cli.command()
@click.argument(
    "package_path", type=click.Path(exists=True, path_type=Path), required=False, default=None
)
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", type=click.Path(path_type=Path), default=Path("diagrams"))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["mmd", "puml", "svg", "all", "mermaid", "plantuml"]),
    default="all",
    help="Format des diagrammes (mermaid/plantuml sont des alias de mmd/puml)",
)
def diagram(package_path: Path | None, config: Path | None, output: Path, fmt: str) -> None:
    """Génère uniquement les diagrammes (sans site)."""

    # vocabulaire aligné sur la config (formats = ["mmd", "puml", ...])
    fmt = {"mermaid": "mmd", "plantuml": "puml"}.get(fmt, fmt)

    cfg = load_config(config_path=config, package_path=package_path)
    cfg.merge_cli(package_path=package_path)

    if not cfg.package_path.exists():
        console.print(f"[red]Erreur: chemin {cfg.package_path} introuvable[/]")
        sys.exit(1)

    console.print(f"Génération diagrammes pour {cfg.package_path} -> {output}")

    try:
        package_info = analyze_package(
            root_path=cfg.package_path,
            package_name=cfg.package_name,
            exclude_patterns=cfg.exclude_patterns,
            include_private=cfg.include_private,
            include_tests=cfg.include_tests,
        )
    except RuntimeError as e:
        console.print(f"[red]Échec analyse: {e}[/]")
        sys.exit(2)
    except Exception as e:
        console.print(f"[red]Erreur inattendue lors de l'analyse: {e}[/]")
        sys.exit(2)

    if package_info.errors:
        console.print(f"[yellow]⚠ {len(package_info.errors)} fichier(s) non parsables ignorés:[/]")
        for err in package_info.errors:
            console.print(f"  [yellow]- {err}[/]")

    output.mkdir(parents=True, exist_ok=True)

    from .renderers import (
        generate_class_diagram_mermaid,
        generate_class_diagram_plantuml,
        generate_class_diagram_svg,
        generate_package_diagram_mermaid,
        generate_package_diagram_plantuml,
        generate_package_diagram_svg,
        save_svg,
    )

    # Package
    if fmt in ("mmd", "all"):
        (output / "package.mmd").write_text(
            generate_package_diagram_mermaid(package_info), encoding="utf-8"
        )
    if fmt in ("puml", "all"):
        (output / "package.puml").write_text(
            generate_package_diagram_plantuml(package_info), encoding="utf-8"
        )
    if fmt in ("svg", "all"):
        save_svg(generate_package_diagram_svg(package_info), output / "package.svg")

    # Global class
    if fmt in ("mmd", "all"):
        (output / "classes.mmd").write_text(
            generate_class_diagram_mermaid(package_info.classes, package_info.relations),
            encoding="utf-8",
        )
    if fmt in ("puml", "all"):
        (output / "classes.puml").write_text(
            generate_class_diagram_plantuml(package_info.classes, package_info.relations),
            encoding="utf-8",
        )
    if fmt in ("svg", "all"):
        save_svg(
            generate_class_diagram_svg(
                package_info.classes, package_info.relations, title="Classes"
            ),
            output / "classes.svg",
        )

    console.print(f"[green]Diagrammes générés dans {output}[/]")


@cli.command()
@click.argument(
    "package_path", type=click.Path(exists=True, path_type=Path), required=False, default=None
)
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path))
def check(package_path: Path | None, config: Path | None) -> None:
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
        if package_info.errors:
            console.print(
                f"[red]✗ Code non analysable: {len(package_info.errors)} fichier(s) en erreur[/]"
            )
            for err in package_info.errors:
                console.print(f"  [red]- {err}[/]")
            sys.exit(1)
        console.print(
            f"[green]✓ Code analysable: {len(package_info.modules)} modules, "
            f"{len(package_info.classes)} classes[/]"
        )
        if package_info.circular_dependencies:
            console.print(
                f"[yellow]⚠ {len(package_info.circular_dependencies)} "
                f"dépendance(s) circulaire(s) détectée(s)[/]"
            )
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]✗ Code non analysable: {e}[/]")
        sys.exit(1)


@cli.command()
@click.argument(
    "package_path", type=click.Path(exists=True, path_type=Path), required=False, default=None
)
@click.option(
    "--config", "-c", type=click.Path(exists=True, path_type=Path), help="Chemin vers gendoc.toml"
)
@click.option("--port", type=int, default=8000, help="Port du serveur de prévisualisation")
def serve(package_path: Path | None, config: Path | None, port: int) -> None:
    """Régénère la documentation puis la sert avec MkDocs.

    Le rechargement automatique de MkDocs ne surveille que les pages générées,
    pas le code source : relancer la commande après modification du code.
    """
    import importlib.util
    import subprocess

    if importlib.util.find_spec("mkdocs") is None:
        console.print(
            "[red]mkdocs est requis pour servir le site : pip install 'gendoc\\[site]'[/]"
        )
        sys.exit(1)

    cfg = load_config(config_path=config, package_path=package_path)
    cfg.merge_cli(package_path=package_path)

    if not cfg.package_path.exists():
        console.print(f"[red]Erreur: chemin {cfg.package_path} introuvable[/]")
        sys.exit(1)

    console.print(f"[bold blue]gendoc[/] - Analyse de [cyan]{cfg.package_path}[/]")
    try:
        package_info = analyze_package(
            root_path=cfg.package_path,
            package_name=cfg.package_name,
            exclude_patterns=cfg.exclude_patterns,
            include_private=cfg.include_private,
            include_tests=cfg.include_tests,
        )
        docs_path = SiteBuilder(cfg, package_info).build()
    except Exception as e:
        console.print(f"[red]Échec de la génération: {e}[/]")
        sys.exit(2)

    mkdocs_yml = docs_path.parent / "mkdocs.yml"
    if not mkdocs_yml.exists():
        console.print(f"[red]mkdocs.yml introuvable à côté de {docs_path}[/]")
        sys.exit(1)

    console.print(
        f"[green]Docs régénérées dans {docs_path}[/] — "
        f"serveur sur [bold]http://127.0.0.1:{port}[/] (Ctrl+C pour arrêter)"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mkdocs",
            "serve",
            "-f",
            str(mkdocs_yml),
            "-a",
            f"127.0.0.1:{port}",
        ],
        env=_mkdocs_env(package_info),
    )
    sys.exit(result.returncode)


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

# Diagramme ciblé (optionnel)
# focus_class = "MaClasse"
# focus_depth = 2

# Site
site_name = "Ma Documentation"
theme = "material"
enable_search = true
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
