"""Tests builder."""

from pathlib import Path

from gendoc.analyzer import analyze_package
from gendoc.builder import SiteBuilder
from gendoc.config import GendocConfig


def test_builder_creates_docs(temp_package, tmp_path: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    cfg = GendocConfig()
    cfg.package_path = temp_package
    cfg.output_dir = tmp_path / "site"
    cfg.docs_dir = tmp_path / "docs"
    cfg.formats = ["mmd", "puml", "svg"]
    cfg.site_name = "Test Docs"

    builder = SiteBuilder(cfg, pkg)
    docs_path = builder.build()

    assert docs_path.exists()
    assert (docs_path / "index.md").exists()
    assert (docs_path / "packages.md").exists()
    assert (docs_path / "diagrams" / "package.mmd").exists()
    assert (docs_path / "diagrams" / "package.puml").exists()
    assert (docs_path / "diagrams" / "package.svg").exists()

    # Modules
    assert (docs_path / "modules").exists()
    modules_files = list((docs_path / "modules").glob("*.md"))
    assert len(modules_files) >= 1

    # API
    assert (docs_path / "api").exists()
    api_files = list((docs_path / "api").glob("*.md"))
    assert len(api_files) >= 1

    # mkdocs.yml
    mkdocs_yml = docs_path.parent / "mkdocs.yml"
    assert mkdocs_yml.exists()
    content = mkdocs_yml.read_text()
    assert "site_name" in content
    assert "mkdocstrings" in content


def test_builder_focus(temp_package, tmp_path: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    cfg = GendocConfig()
    cfg.package_path = temp_package
    cfg.output_dir = tmp_path / "site"
    cfg.docs_dir = tmp_path / "docs"
    cfg.formats = ["mmd", "svg"]
    cfg.focus_class = "User"
    cfg.focus_depth = 1

    builder = SiteBuilder(cfg, pkg)
    docs_path = builder.build()

    assert (docs_path / "focus.md").exists()
    assert (docs_path / "diagrams" / "focus_User.mmd").exists()
    assert (docs_path / "diagrams" / "focus_User.svg").exists()

    focus_content = (docs_path / "focus.md").read_text()
    assert "User" in focus_content


def test_builder_public_only(temp_package, tmp_path: Path):
    pkg = analyze_package(temp_package, package_name="testpkg")

    cfg = GendocConfig()
    cfg.package_path = temp_package
    cfg.output_dir = tmp_path / "site"
    cfg.docs_dir = tmp_path / "docs"
    cfg.public_only = True

    builder = SiteBuilder(cfg, pkg)
    docs_path = builder.build()

    assert (docs_path / "index.md").exists()
