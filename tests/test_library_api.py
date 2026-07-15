"""Tests pour usage comme librairie Python."""

from pathlib import Path

import gendoc


def test_import_as_library():
    from importlib.metadata import version

    assert hasattr(gendoc, "__version__")
    # version unique, lue depuis les métadonnées du package installé
    assert gendoc.__version__ == version("gendoc")


def test_cli_version_matches_package():
    from importlib.metadata import version

    from click.testing import CliRunner

    from gendoc.cli import cli

    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert version("gendoc") in result.output


def test_analyze_api(temp_package: Path):
    pkg = gendoc.analyze(temp_package, package_name="testpkg")
    assert len(pkg.modules) >= 2
    assert len(pkg.classes) >= 1


def test_build_docs_api(temp_package: Path, tmp_path: Path):
    docs_path = gendoc.build_docs(
        temp_package,
        output_dir=tmp_path / "site",
        docs_dir=tmp_path / "docs",
        site_name="Test Lib",
    )
    assert docs_path.exists()
    assert (docs_path / "index.md").exists()
    assert (docs_path / "diagrams" / "package.mmd").exists()


def test_get_diagrams_api(temp_package: Path):
    diags = gendoc.get_diagrams(temp_package, diagram_format="mermaid")
    assert "package" in diags
    assert "classes" in diags
    assert "classDiagram" in diags["classes"]
    assert "flowchart" in diags["package"]

    diags_puml = gendoc.get_diagrams(temp_package, diagram_format="plantuml")
    assert "@startuml" in diags_puml["package"]

    diags_svg = gendoc.get_diagrams(temp_package, diagram_format="svg")
    assert "<svg" in diags_svg["package"]


def test_get_diagrams_unknown_format_raises(temp_package: Path):
    import pytest

    with pytest.raises(ValueError, match="Format inconnu"):
        gendoc.get_diagrams(temp_package, diagram_format="dot")


def test_get_diagrams_focus_plantuml_and_svg(temp_package: Path):
    puml = gendoc.get_diagrams(temp_package, "plantuml", focus_class="User", depth=1)
    assert "@startuml" in puml["focus_User"]

    svg = gendoc.get_diagrams(temp_package, "svg", focus_class="User", depth=1)
    assert "<svg" in svg["focus_User"]


def test_get_diagrams_focus(temp_package: Path):
    diags = gendoc.get_diagrams(temp_package, "mermaid", focus_class="User", depth=1)
    assert "focus_User" in diags
    assert "User" in diags["focus_User"]


def test_check_package(temp_package: Path):
    assert gendoc.check_package(temp_package) is True

    # mauvais chemin
    assert gendoc.check_package("/tmp/nonexistent_xyz") is False


def test_quick_overview(temp_package: Path):
    overview = gendoc.quick_overview(temp_package)
    assert "Modules" in overview
    assert "Classes" in overview


def test_analyze_public_only_filters_members(tmp_path: Path):
    """analyze(public_only=True) retire les membres non publics des classes."""
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "m.py").write_text(
        "class C:\n"
        "    x: int = 1\n"
        "    _y: int = 2\n"
        "    def pub(self):\n        pass\n"
        "    def _priv(self):\n        pass\n"
    )

    pkg = gendoc.analyze(pkg_dir, public_only=True)

    c = pkg.classes["pkg.m.C"]
    assert {m.name for m in c.methods} == {"pub"}
    assert {a.name for a in c.attributes} == {"x"}


def test_get_diagrams_accepts_preanalyzed_package(temp_package: Path):
    """get_diagrams peut réutiliser un PackageInfo déjà analysé (pas de ré-analyse)."""
    pkg = gendoc.analyze(temp_package, package_name="testpkg")

    diags = gendoc.get_diagrams(package_info=pkg)

    assert "package" in diags
    assert "classes" in diags


def test_build_with_config_api(temp_package: Path, tmp_path: Path):
    cfg = gendoc.GendocConfig(
        package_path=temp_package,
        output_dir=tmp_path / "site2",
        docs_dir=tmp_path / "docs2",
        site_name="Config Test",
        public_only=True,
    )
    docs_path = gendoc.build_docs_with_config(cfg)
    assert docs_path.exists()
