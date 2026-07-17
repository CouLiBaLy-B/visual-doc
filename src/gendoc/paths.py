"""Source unique des chemins d'import rendant un package analysé importable.

Consommé par la CLI (PYTHONPATH du sous-processus mkdocs) et par le builder
(clé ``paths`` de mkdocstrings dans mkdocs.yml) : une seule liste de
candidats, chaque consommateur choisit sa sérialisation.
"""

from __future__ import annotations

from pathlib import Path


def compute_import_paths(package_root: Path, cwd: Path | None = None) -> list[Path]:
    """Chemins candidats (absolus, dédupliqués, ordre stable) pour importer le package.

    Couvre les layouts usuels : package sous le CWD, package pointé ailleurs,
    src-layout (``src/``), et package imbriqué (``parent.parent`` pour les
    imports en ``pkg.sous_pkg``).
    """
    base = (cwd or Path.cwd()).resolve()
    paths = [base]
    try:
        pkg_root = package_root.resolve()
        paths.extend([pkg_root.parent, pkg_root, pkg_root.parent.parent])
    except OSError:
        pass
    src_path = base / "src"
    if src_path.exists():
        paths.append(src_path.resolve())
    return list(dict.fromkeys(paths))
