"""Analyseur de package complet."""
from __future__ import annotations

import fnmatch
from pathlib import Path

from .ast_parser import parse_module
from .cache import ParseCache
from .models import ModuleInfo, PackageInfo
from .relationships import detect_circular_dependencies, detect_relationships


def _is_excluded(path: Path, exclude_patterns: list[str], root: Path) -> bool:
    """Vérifie si un fichier doit être exclu.

    Un pattern sans "/" est comparé (fnmatch) à chaque segment du chemin relatif ;
    un pattern avec "/" est comparé au chemin relatif complet. Pas de match par
    sous-chaîne : "test" n'exclut pas "attestation.py".
    """
    rel = path.relative_to(root)
    rel_str = str(rel).replace("\\", "/")
    for pattern in exclude_patterns:
        if "/" in pattern:
            if fnmatch.fnmatch(rel_str, pattern):
                return True
        elif any(fnmatch.fnmatch(part, pattern) for part in rel.parts):
            return True
    return False


def get_module_dotted_path(file_path: Path, root_path: Path, package_name: str) -> str:
    """Calcule le dotted path d'un module."""
    rel = file_path.relative_to(root_path)
    parts = list(rel.parts)
    # enlever .py
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    else:
        # enlever extension
        parts[-1] = parts[-1][:-3]
    if not parts:
        return package_name
    return f"{package_name}.{'.'.join(parts)}"


def analyze_package(
    root_path: Path | str,
    package_name: str | None = None,
    exclude_patterns: list[str] | None = None,
    include_private: bool = False,
    include_tests: bool = False,
    strict: bool = False,
    cache_dir: Path | str | None = None,
) -> PackageInfo:
    """Analyse un package Python complet.

    Args:
        root_path: Package, dossier parent (layout src/) ou fichier unique.
        package_name: Nom du package (auto-détecté sinon).
        exclude_patterns: Patterns d'exclusion (segments de chemin, fnmatch).
        include_private: Inclure les classes/fonctions préfixées par `_`.
        include_tests: Inclure les fichiers/dossiers de tests.
        strict: Si True, un fichier non parsable fait échouer l'analyse
            (RuntimeError). Sinon il est ignoré et listé dans PackageInfo.errors.
        cache_dir: Si fourni, cache disque du parsing : les fichiers dont le
            contenu n'a pas changé (sha256) ne sont pas re-parsés.
    """

    root_path = Path(root_path).resolve()
    if not root_path.exists():
        raise ValueError(f"Chemin introuvable: {root_path}")

    exclude_patterns = list(exclude_patterns) if exclude_patterns else []

    if root_path.is_file():
        analysis_root = root_path.parent
        pkg_name = package_name or analysis_root.name
        files = [root_path]
    else:
        analysis_root = root_path
        # Layout src/ : si le dossier pointé n'est pas un package et contient
        # exactement un package enfant, on descend dedans (sinon les dotted
        # paths deviendraient "src.mypkg.mod").
        if package_name is None and not (analysis_root / "__init__.py").exists():
            child_packages = sorted(
                d
                for d in analysis_root.iterdir()
                if d.is_dir() and (d / "__init__.py").exists() and not d.name.startswith(".")
            )
            if len(child_packages) == 1:
                analysis_root = child_packages[0]
        pkg_name = package_name or analysis_root.name

        default_excludes = []
        if not include_tests:
            default_excludes = ["test_*", "*_test.py", "tests", "test", "testing"]
        all_excludes = exclude_patterns + [p for p in default_excludes if p not in exclude_patterns]

        files = []
        for py_file in sorted(analysis_root.rglob("*.py")):
            if any(
                part in {".git", ".venv", "venv", "__pycache__", "build", "dist", ".mypy_cache"}
                for part in py_file.parts
            ):
                continue
            if _is_excluded(py_file, all_excludes, analysis_root):
                continue
            files.append(py_file)

    package_info = PackageInfo(name=pkg_name, root_path=analysis_root)
    cache = ParseCache(Path(cache_dir)) if cache_dir else None

    # Première passe : parser chaque fichier (une seule passe AST par fichier)
    for file_path in files:
        dotted = get_module_dotted_path(file_path, analysis_root, pkg_name)

        try:
            parsed = None
            source: bytes | None = None
            if cache is not None:
                try:
                    source = file_path.read_bytes()
                except OSError:
                    source = None
                if source is not None:
                    parsed = cache.get(file_path, dotted, source)
            if parsed is None:
                parsed = parse_module(file_path, dotted)
                if cache is not None and source is not None:
                    cache.put(file_path, dotted, source, parsed)
        except ValueError as e:
            if strict:
                raise RuntimeError(f"Code non analysable dans {file_path}: {e}") from e
            package_info.errors.append(f"{file_path}: {e}")
            continue

        classes = parsed.classes
        functions = parsed.functions
        if not include_private:
            classes = [
                c for c in classes if not any(part.startswith("_") for part in c.name.split("."))
            ]
            functions = [f for f in functions if not f.name.startswith("_")]

        # Séparer imports internes/externes (frontière de nom stricte)
        internal: list[str] = []
        external: list[str] = []
        for imp in parsed.imports:
            if imp.startswith(".") or imp == pkg_name or imp.startswith(pkg_name + "."):
                internal.append(imp)
            elif _is_potential_internal(imp, files, analysis_root, pkg_name):
                internal.append(imp)
            else:
                external.append(imp)

        module_info = ModuleInfo(
            name=file_path.stem,
            file_path=file_path,
            dotted_path=dotted,
            classes=classes,
            functions=functions,
            imports=parsed.imports,
            internal_imports=internal,
            external_imports=external,
            docstring=parsed.docstring,
        )

        package_info.modules[dotted] = module_info
        for cls in classes:
            package_info.classes[cls.qualified_name] = cls

    # Deuxième passe : graphe des dépendances inter-modules
    dependencies: dict[str, set[str]] = {}
    for dotted, mod in package_info.modules.items():
        deps = set()
        is_package = mod.file_path.name == "__init__.py"
        for imp in mod.internal_imports:
            normalized = _normalize_import(imp, dotted, pkg_name, is_package=is_package)
            target = _resolve_import_target(normalized, package_info.modules, pkg_name)
            if target and target != dotted:
                deps.add(target)
        dependencies[dotted] = deps

    package_info.dependencies = dependencies
    package_info.circular_dependencies = detect_circular_dependencies(dependencies)
    package_info.relations = detect_relationships(
        list(package_info.classes.values()), warnings=package_info.warnings
    )

    return package_info


def _is_potential_internal(imp: str, files: list[Path], root: Path, pkg_name: str) -> bool:
    """Heuristique pour savoir si un import est interne."""
    # si imp est "example_pkg.models", et on a fichier models.py
    # on vérifie existence
    # imp simple: "models" => vérifier si root/models.py ou root/pkg/models.py exists
    # imp dotted: "services.foo"
    imp_path = imp.replace(".", "/")
    # Check direct file
    candidates = [
        root / f"{imp_path}.py",
        root / imp_path / "__init__.py",
    ]
    for cand in candidates:
        if cand.exists():
            return True
    # Check si dernier part correspond à un fichier existant
    last = imp.split(".")[-1]
    for f in files:
        if f.stem == last:
            return True
    return False


def _normalize_import(
    imp: str, current_dotted: str, pkg_name: str, is_package: bool = False
) -> str:
    """Normalise un import relatif en absolu.

    Args:
        is_package: True si le module courant est un __init__.py — le contexte
            relatif est alors le package lui-même, pas son parent (sinon
            `from . import x` dans pkg/sub/__init__.py résoudrait vers pkg.x).
    """
    if not imp.startswith("."):
        return imp
    level = len(imp) - len(imp.lstrip("."))
    module_part = imp.lstrip(".")

    current_parts = current_dotted.split(".")
    context = current_parts if is_package else current_parts[:-1]
    # level 1 = package courant ; chaque niveau supplémentaire remonte d'un cran
    base = context[: len(context) - (level - 1)] if level > 1 else context
    if not base:
        base = [pkg_name]
    return ".".join(base + [module_part]) if module_part else ".".join(base)


def _resolve_import_target(
    normalized: str, modules: dict[str, ModuleInfo], pkg_name: str
) -> str | None:
    """Résout l'import vers un module existant (candidats parcourus en ordre trié)."""
    if normalized in modules:
        return normalized
    if not normalized.startswith(pkg_name):
        with_pkg = f"{pkg_name}.{normalized}"
        if with_pkg in modules:
            return with_pkg
    for mod_name in sorted(modules):
        if mod_name.endswith(f".{normalized}"):
            return mod_name
    # dernier recours : match sur le dernier composant
    last = normalized.split(".")[-1]
    candidates = sorted(m for m in modules if m.split(".")[-1] == last)
    if candidates:
        return candidates[0]
    return None
