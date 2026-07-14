"""Tests pour usage comme librairie Python."""

from pathlib import Path

import gendoc


def test_import_as_library():
    assert hasattr(gendoc, "__version__")
    assert gendoc.__version__ == "0.1.0"


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
    assert "classDiagram" in diags["classes"] or "flowchart" in diags["package"]

    diags_puml = gendoc.get_diagrams(temp_package, diagram_format="plantuml")
    assert "@startuml" in diags_puml["package"]

    diags_svg = gendoc.get_diagrams(temp_package, diagram_format="svg")
    assert "<svg" in diags_svg["package"]


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
