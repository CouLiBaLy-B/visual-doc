"""Analyseur de package complet."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Optional

from .ast_parser import parse_file_for_classes, parse_module_imports
from .models import ModuleInfo, PackageInfo, RelationInfo, RelationType
from .relationships import detect_relationships, detect_circular_dependencies


def _is_excluded(path: Path, exclude_patterns: list[str], root: Path) -> bool:
    """Vérifie si un fichier doit être exclu."""
    rel = str(path.relative_to(root)).replace("\\", "/")
    name = path.name
    for pattern in exclude_patterns:
        # patterns simples: glob style simplifié
        if pattern in rel:
            return True
        if pattern == "__pycache__" and "__pycache__" in rel:
            return True
        # check fnmatch-like
        import fnmatch

        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
            return True
    return False


def _should_ignore_private(name: str, include_private: bool) -> bool:
    if include_private:
        return False
    # ignorer fichiers commençant par _
    # mais pas __init__.py
    if name.startswith("_") and name not in ("__init__.py", "__main__.py"):
        # autoriser _private.py si include_private false ? on l'exclut
        # on exclut si commence par _ ou tests
        # On va laisser la logique à exclude_patterns; ici filtre simple
        pass
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
    root_path: Path,
    package_name: Optional[str] = None,
    exclude_patterns: Optional[list[str]] = None,
    include_private: bool = False,
    include_tests: bool = False,
) -> PackageInfo:
    """Analyse un package Python complet."""

    root_path = root_path.resolve()
    if not root_path.exists():
        raise ValueError(f"Chemin introuvable: {root_path}")

    # Déterminer package_name et root
    # Si root_path est un fichier, prendre parent
    # Si c'est un dossier avec __init__.py, son nom est package_name
    # Si c'est un dossier sans __init__, on analyse récursivement
    if root_path.is_file():
        # analyser un seul fichier ? On prend son parent comme root
        analysis_root = root_path.parent
        pkg_name = package_name or analysis_root.name
        files = [root_path]
    else:
        analysis_root = root_path
        pkg_name = package_name or analysis_root.name
        if exclude_patterns is None:
            exclude_patterns = []
        # Ajouter exclusions par défaut si nécessaire
        default_excludes = []
        if not include_tests:
            default_excludes.extend(["test_*", "*_test.py", "tests", "test", "testing"])
        if not include_private:
            # on n'exclut pas forcément les fichiers privés ici, mais on peut filtrer plus tard
            pass
        all_excludes = list(set(exclude_patterns + default_excludes))

        # Collecte des fichiers .py
        files = []
        for py_file in analysis_root.rglob("*.py"):
            if _is_excluded(py_file, all_excludes, analysis_root):
                continue
            # exclure venv, .git etc
            if any(part in {".git", ".venv", "venv", "__pycache__", "build", "dist", ".mypy_cache"} for part in py_file.parts):
                continue
            files.append(py_file)

    if exclude_patterns is None:
        exclude_patterns = []

    package_info = PackageInfo(name=pkg_name, root_path=analysis_root)

    # Première passe: analyser chaque fichier pour modules et classes
    for file_path in files:
        if file_path.name == "__pycache__":
            continue
        dotted = get_module_dotted_path(file_path, analysis_root, pkg_name)

        # Filtre privé sur fichier
        if not include_private:
            # si fichier contient "private" ou commence par _ (hors __init__)
            if file_path.name.startswith("_") and file_path.name != "__init__.py":
                if not any(p in str(file_path) for p in exclude_patterns):
                    # On exclut si include_private false
                    # Mais respecter si utilisateur veut explicitement
                    # Simplifions: exclure
                    continue

        try:
            classes = parse_file_for_classes(file_path, dotted)
            imports = parse_module_imports(file_path)
        except ValueError as e:
            # erreur de parsing => on fait échouer le build selon spec
            raise RuntimeError(f"Code non analysable dans {file_path}: {e}") from e

        # Séparer imports internes/externes
        internal: list[str] = []
        external: list[str] = []
        for imp in imports:
            # considérer interne si commence par pkg_name ou relatif
            if imp.startswith(".") or imp.startswith(pkg_name):
                internal.append(imp)
            else:
                # Vérifier si c'est un sous-module du package
                # si le module existe en local
                # Simplification: si imp contient pkg_name ou si dotted file existe
                # On va checker si un fichier correspond
                # On garde aussi heuristique: si imp est dans les modules connus plus tard, on reclasse
                # Pour l'instant, tout ce qui ne commence pas par pkg_name est externe
                # Mais on garde aussi possibilité que import soit "models" -> interne si file exists
                # Implementons petite heuristique
                if _is_potential_internal(imp, files, analysis_root, pkg_name):
                    internal.append(imp)
                else:
                    external.append(imp)

        module_info = ModuleInfo(
            name=file_path.stem,
            file_path=file_path,
            dotted_path=dotted,
            classes=classes,
            imports=imports,
            internal_imports=internal,
            external_imports=external,
        )

        package_info.modules[dotted] = module_info
        for cls in classes:
            package_info.classes[cls.qualified_name] = cls

    # Deuxième passe: dépendances inter-modules
    # Construire graph des dépendances
    dependencies: dict[str, set[str]] = {}
    for dotted, mod in package_info.modules.items():
        deps = set()
        for imp in mod.internal_imports:
            # Normaliser import relatif
            normalized = _normalize_import(imp, dotted, pkg_name)
            # Trouver module cible le plus proche
            target = _resolve_import_target(normalized, package_info.modules, pkg_name)
            if target and target != dotted:
                deps.add(target)
        # Aussi via composition ? Non, dépendance = import
        dependencies[dotted] = deps

    package_info.dependencies = dependencies

    # Détection circulaire
    package_info.circular_dependencies = detect_circular_dependencies(dependencies)

    # Détection relations entre classes
    package_info.relations = detect_relationships(list(package_info.classes.values()))

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


def _normalize_import(imp: str, current_dotted: str, pkg_name: str) -> str:
    """Normalise un import relatif en absolu."""
    if not imp.startswith("."):
        return imp
    # compter dots
    level = len(imp) - len(imp.lstrip("."))
    module_part = imp.lstrip(".")

    # current_dotted: e.g., example_pkg.sub.models
    # on doit remonter level-1
    current_parts = current_dotted.split(".")
    # Si dans package __init__, current_parts[-1] == package_name, on remonte différemment
    # Simplification: remonter level fois
    if level > 1:
        base = current_parts[:-level]
    else:
        # from . import x => même package
        base = current_parts[:-1]
    if not base:
        base = [pkg_name]
    if module_part:
        return ".".join(base + [module_part])
    else:
        return ".".join(base)


def _resolve_import_target(normalized: str, modules: dict[str, "ModuleInfo"], pkg_name: str) -> Optional[str]:
    """Résout l'import vers un module existant."""
    if normalized in modules:
        return normalized
    # essayer préfixe pkg_name
    if not normalized.startswith(pkg_name):
        with_pkg = f"{pkg_name}.{normalized}"
        if with_pkg in modules:
            return with_pkg
    # chercher le plus long préfixe correspondant
    # ex: normalized = "example_pkg.models" et modules contient "example_pkg.models"
    # ou normalized = "models" -> chercher *models
    for mod_name in modules:
        if mod_name.endswith(f".{normalized}") or mod_name == normalized:
            return mod_name
        if normalized in mod_name:
            # fallback
            pass
    # chercher par suffixe
    candidates = [m for m in modules if m.split(".")[-1] == normalized.split(".")[-1]]
    if candidates:
        return candidates[0]
    return None
