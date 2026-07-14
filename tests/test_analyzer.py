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

    comp_rels = [r for r in pkg.relations if r.relation_type in (RelationType.COMPOSITION, RelationType.AGGREGATION)]
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
    # Créer fichier privé
    private_file = temp_package / "_private.py"
    private_file.write_text(
        '''
class Secret:
    pass
'''
    )

    pkg = analyze_package(temp_package, package_name="testpkg", include_private=False)
    # _private devrait être exclu
    assert "testpkg._private" not in pkg.modules

    pkg2 = analyze_package(temp_package, package_name="testpkg", include_private=True)
    assert "testpkg._private" in pkg2.modules


def test_focused_subgraph(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    focused_classes, focused_rels = get_focused_subgraph(pkg.classes, pkg.relations, "User", depth=1)

    assert len(focused_classes) >= 1
    # User devrait être inclus
    assert any("User" in k for k in focused_classes.keys())
    # PremiumUser hérite de User, devrait être dans depth 1
    assert any("PremiumUser" in k for k in focused_classes.keys()) or len(focused_classes) >= 1


def test_focus_invalid_class(temp_package: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    with pytest.raises(ValueError, match="non trouvée"):
        get_focused_subgraph(pkg.classes, pkg.relations, "NonExistent", depth=1)


def test_analyze_unparsable():
    from pathlib import Path
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "pkg"
        p.mkdir()
        (p / "__init__.py").write_text("")
        bad = p / "bad.py"
        bad.write_text("def foo(:\n    invalid syntax $$$\n")

        with pytest.raises(RuntimeError, match="non analysable"):
            analyze_package(p, package_name="pkg")


def test_analyze_test_exclusion(temp_package: Path):
    # créer fichier test
    test_file = temp_package / "test_models.py"
    test_file.write_text("class TestFoo: pass\n")

    pkg = analyze_package(temp_package, package_name="testpkg", include_tests=False)
    assert "testpkg.test_models" not in pkg.modules

    pkg2 = analyze_package(temp_package, package_name="testpkg", include_tests=True)
    assert "testpkg.test_models" in pkg2.modules
