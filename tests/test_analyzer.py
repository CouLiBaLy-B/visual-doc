"""Tests analyzer."""

from pathlib import Path

import pytest

from gendoc.analyzer import analyze_package, get_focused_subgraph
from gendoc.analyzer.models import RelationType


def test_analyze_package_basic(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    assert len(pkg.modules) >= 2
    assert "testpkg.models" in pkg.modules
    assert "testpkg.services" in pkg.modules

    assert len(pkg.classes) >= 4
    # Vérifier classes attendues
    class_names = {c.name for c in pkg.classes.values()}
    assert "User" in class_names
    assert "Product" in class_names
    assert "Order" in class_names
    assert "PremiumUser" in class_names


def test_analyze_package_inheritance(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    # Vérifier relation héritage PremiumUser -> User
    inherit_rels = [r for r in pkg.relations if r.relation_type == RelationType.INHERITANCE]
    assert len(inherit_rels) >= 1
    # trouver PremiumUser hérite User
    found = any("PremiumUser" in r.source and "User" in r.target for r in inherit_rels)
    assert found


def test_analyze_package_composition(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    comp_rels = [
        r
        for r in pkg.relations
        if r.relation_type in (RelationType.COMPOSITION, RelationType.AGGREGATION)
    ]
    # Order a Product, UserService a User etc.
    assert len(comp_rels) >= 1


def test_analyze_package_dependencies(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    # services dépend de models via import
    assert "testpkg.services" in pkg.dependencies
    deps = pkg.dependencies["testpkg.services"]
    # devrait dépendre de testpkg.models
    assert any("testpkg.models" in d for d in deps)


def test_circular_detection(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    # On a circular_a <-> circular_b
    assert len(pkg.circular_dependencies) >= 1
    # Vérifier que cycle contient circular_a et circular_b
    cycle_str = " ".join([" ".join(c) for c in pkg.circular_dependencies])
    assert "circular_a" in cycle_str or "circular_b" in cycle_str


def test_analyze_private_filter(temp_package: Path):
    """include_private filtre les classes privées, pas les modules entiers.

    Une classe publique dans un module _privé reste documentée (elle est souvent
    ré-exportée via __init__) ; seules les classes _privées sont masquées.
    """
    private_file = temp_package / "_private.py"
    private_file.write_text(
        '''
class Secret:
    pass

class _Hidden:
    pass
'''
    )

    pkg = analyze_package(temp_package, package_name="testpkg", include_private=False)
    assert "testpkg._private" in pkg.modules
    class_names = {c.name for c in pkg.classes.values()}
    assert "Secret" in class_names
    assert "_Hidden" not in class_names

    pkg2 = analyze_package(temp_package, package_name="testpkg", include_private=True)
    assert "_Hidden" in {c.name for c in pkg2.classes.values()}


def test_focused_subgraph(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    focused_classes, focused_rels = get_focused_subgraph(
        pkg.classes, pkg.relations, "User", depth=1
    )

    # User est le centre du sous-graphe
    assert "testpkg.models.User" in focused_classes
    # PremiumUser hérite de User : présent à depth 1
    assert "testpkg.models.PremiumUser" in focused_classes


def test_focus_invalid_class(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    with pytest.raises(ValueError, match="non trouvée"):
        get_focused_subgraph(pkg.classes, pkg.relations, "NonExistent", depth=1)


def test_analyze_unparsable_tolerant_by_default(tmp_path: Path):
    """Par défaut, un fichier non parsable est collecté dans errors sans faire échouer l'analyse."""
    p = tmp_path / "pkg"
    p.mkdir()
    (p / "__init__.py").write_text("")
    (p / "good.py").write_text("class Good:\n    pass\n")
    (p / "bad.py").write_text("def foo(:\n    invalid syntax $$$\n")

    pkg = analyze_package(p, package_name="pkg")

    assert "pkg.good" in pkg.modules
    assert "pkg.bad" not in pkg.modules
    assert len(pkg.errors) == 1
    assert "bad.py" in pkg.errors[0]


def test_analyze_unparsable_strict_raises(tmp_path: Path):
    """En mode strict, un fichier non parsable fait échouer l'analyse (comportement CI)."""
    p = tmp_path / "pkg"
    p.mkdir()
    (p / "__init__.py").write_text("")
    (p / "bad.py").write_text("def foo(:\n    invalid syntax $$$\n")

    with pytest.raises(RuntimeError, match="non analysable"):
        analyze_package(p, package_name="pkg", strict=True)


def test_module_functions_and_docstring_extracted(tmp_path: Path):
    """Les fonctions top-level et le docstring du module sont extraits."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "utils.py").write_text(
        '"""Utilitaires."""\n\n'
        "def slugify(text: str) -> str:\n    return text\n\n"
        "async def afetch():\n    pass\n"
    )

    pkg = analyze_package(pkg_dir, package_name="pkg")
    mod = pkg.modules["pkg.utils"]

    assert mod.docstring == "Utilitaires."
    assert {f.name for f in mod.functions} == {"slugify", "afetch"}


def test_relative_import_in_package_init_resolves_locally(tmp_path: Path):
    """from . import mod dans pkg/sub/__init__.py doit pointer sur pkg.sub.mod, pas pkg.mod."""
    root = tmp_path / "pkg"
    sub = root / "sub"
    sub.mkdir(parents=True)
    (root / "__init__.py").write_text("")
    (root / "mod.py").write_text("class RootM:\n    pass\n")
    (sub / "__init__.py").write_text("from . import mod\n")
    (sub / "mod.py").write_text("class SubM:\n    pass\n")

    pkg = analyze_package(root, package_name="pkg")
    deps = pkg.dependencies["pkg.sub"]

    assert "pkg.sub.mod" in deps
    assert "pkg.mod" not in deps


def test_similarly_named_external_import_is_external(tmp_path: Path):
    """import example_pkg n'est pas interne au package 'example' (frontière de nom)."""
    pkg_dir = tmp_path / "example"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "mod.py").write_text("import example_pkg\n\nclass C:\n    pass\n")

    pkg = analyze_package(pkg_dir, package_name="example")
    mod = pkg.modules["example.mod"]

    assert "example_pkg" in mod.external_imports
    assert "example_pkg" not in mod.internal_imports


def test_src_layout_autodetects_package(tmp_path: Path):
    """Analyser src/ contenant un unique package descend dans le package."""
    src = tmp_path / "src"
    pkg_dir = src / "mypkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "core.py").write_text("class Core:\n    pass\n")

    info = analyze_package(src)

    assert info.name == "mypkg"
    assert "mypkg.core" in info.modules


def test_exclude_patterns_do_not_match_substrings(tmp_path: Path):
    """Les patterns d'exclusion ne matchent pas par sous-chaîne ('test' vs 'attestation')."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "attestation.py").write_text("class Attestation:\n    pass\n")
    (pkg_dir / "latest.py").write_text("class Latest:\n    pass\n")

    pkg = analyze_package(pkg_dir, package_name="pkg", include_tests=False)

    assert "pkg.attestation" in pkg.modules
    assert "pkg.latest" in pkg.modules
    assert "pkg.attestation.Attestation" in pkg.classes


def test_test_directories_still_excluded(tmp_path: Path):
    """Les vrais répertoires/fichiers de tests restent exclus par défaut."""
    pkg_dir = tmp_path / "pkg"
    (pkg_dir / "tests").mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "mod.py").write_text("class Mod:\n    pass\n")
    (pkg_dir / "tests" / "__init__.py").write_text("")
    (pkg_dir / "tests" / "test_mod.py").write_text("class TestMod:\n    pass\n")

    pkg = analyze_package(pkg_dir, package_name="pkg", include_tests=False)

    assert "pkg.mod" in pkg.modules
    assert not any(".tests" in m or m.endswith("test_mod") for m in pkg.modules)


def test_analyze_test_exclusion(temp_package: Path):
    # créer fichier test
    test_file = temp_package / "test_models.py"
    test_file.write_text("class TestFoo: pass\n")

    pkg = analyze_package(temp_package, package_name="testpkg", include_tests=False)
    assert "testpkg.test_models" not in pkg.modules

    pkg2 = analyze_package(temp_package, package_name="testpkg", include_tests=True)
    assert "testpkg.test_models" in pkg2.modules
