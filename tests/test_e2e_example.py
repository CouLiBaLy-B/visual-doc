"""Tests de bout en bout sur le vrai package d'exemple (example/example_pkg)."""

import os
import re
import subprocess
import sys
from pathlib import Path

from gendoc.analyzer import analyze_package
from gendoc.analyzer.models import RelationType
from gendoc.builder import SiteBuilder
from gendoc.config import GendocConfig

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_PKG = REPO_ROOT / "example" / "example_pkg"


def test_example_pkg_full_analysis():
    pkg = analyze_package(EXAMPLE_PKG, package_name="example_pkg")

    assert pkg.errors == []
    assert {
        "example_pkg",
        "example_pkg.models",
        "example_pkg.services",
        "example_pkg.utils",
        "example_pkg.circular_a",
        "example_pkg.circular_b",
    } <= set(pkg.modules)

    names = {c.name for c in pkg.classes.values()}
    expected = {"Product", "User", "PremiumUser", "OrderItem", "Order"}
    expected |= {"UserService", "OrderService"}
    assert expected <= names

    # héritage résolu vers la classe du même module
    assert any(
        r.source == "example_pkg.models.PremiumUser"
        and r.target == "example_pkg.models.User"
        and r.relation_type == RelationType.INHERITANCE
        for r in pkg.relations
    )

    # le cycle circular_a <-> circular_b est détecté, une seule fois, sans endpoint dupliqué
    assert len(pkg.circular_dependencies) == 1
    cycle = pkg.circular_dependencies[0]
    assert sorted(cycle) == ["example_pkg.circular_a", "example_pkg.circular_b"]

    # fonctions de module extraites avec leur docstring
    utils = pkg.modules["example_pkg.utils"]
    assert "format_price" in {f.name for f in utils.functions}
    assert utils.docstring is not None


def test_example_pkg_docs_build_is_consistent(tmp_path: Path, monkeypatch):
    """Build complet : liens d'images valides, pas de chemins machine, fonctions listées."""
    monkeypatch.chdir(tmp_path)
    pkg = analyze_package(EXAMPLE_PKG, package_name="example_pkg")

    cfg = GendocConfig(
        package_path=EXAMPLE_PKG,
        docs_dir=tmp_path / "docs",
        output_dir=tmp_path / "site",
        site_name="Demo e2e",
    )
    docs = SiteBuilder(cfg, pkg).build()

    pages = list(docs.rglob("*.md"))
    assert pages
    for page in pages:
        text = page.read_text()
        # tous les liens d'images pointent vers des fichiers existants
        for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", text):
            target = (page.parent / match.group(1)).resolve()
            assert target.exists(), f"{page}: image cassée -> {match.group(1)}"
        # aucun chemin absolu de la machine dans les docs
        assert str(EXAMPLE_PKG) not in text, page

    utils_page = (docs / "modules" / "example_pkg_utils.md").read_text()
    assert "format_price" in utils_page

    # l'index signale le cycle, refermé pour lisibilité (a -> b -> a)
    index = (docs / "index.md").read_text()
    assert "circular_a" in index and "circular_b" in index


def test_diagrams_deterministic_across_hash_seeds():
    """Deux processus avec des seeds de hash différents produisent les mêmes diagrammes."""
    code = (
        "import sys, gendoc;"
        "pkg = gendoc.analyze(sys.argv[1], package_name='example_pkg');"
        "d = gendoc.get_diagrams(package_info=pkg);"
        "print(d['classes']);"
        "print(d['package'])"
    )
    outputs = []
    for seed in ("1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", code, str(EXAMPLE_PKG)],
            capture_output=True,
            text=True,
            env=env,
            cwd=REPO_ROOT,
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)

    assert outputs[0] == outputs[1]


def test_example_pkg_relation_semantics():
    """Verrouille la sémantique validée sur l'exemple : composition = construit par
    la classe, agrégation = collection reçue, association = référence stockée."""
    pkg = analyze_package(EXAMPLE_PKG, package_name="example_pkg")

    rels = {(r.source, r.target): r.relation_type for r in pkg.relations}
    m, s = "example_pkg.models.", "example_pkg.services."

    # dataclass : conteneur construit via field(default_factory=list)
    assert rels[(m + "Order", m + "OrderItem")] == RelationType.COMPOSITION
    # références injectées par le constructeur généré
    assert rels[(m + "Order", m + "User")] == RelationType.ASSOCIATION
    assert rels[(m + "OrderItem", m + "Product")] == RelationType.ASSOCIATION
    # self.x = param (référence stockée)
    assert rels[(s + "OrderService", s + "UserService")] == RelationType.ASSOCIATION
    # self.xs: List[X] = [] (conteneur construit dans __init__)
    assert rels[(s + "OrderService", m + "Order")] == RelationType.COMPOSITION
    assert rels[(s + "UserService", m + "User")] == RelationType.COMPOSITION
