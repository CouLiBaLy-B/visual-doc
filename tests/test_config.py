"""Tests config."""

from pathlib import Path

from gendoc.config import GendocConfig, load_config


def test_default_config():
    cfg = GendocConfig()

    assert cfg.package_path == Path(".")
    assert "mmd" in cfg.formats
    assert cfg.focus_depth == 2


def test_config_from_toml(tmp_path: Path):
    toml_content = """
[gendoc]
package_path = "src"
package_name = "mypkg"
output_dir = "out"
formats = ["mmd", "svg"]
include_private = true
public_only = true
site_name = "Test Site"
"""

    toml_file = tmp_path / "gendoc.toml"
    toml_file.write_text(toml_content)

    cfg = GendocConfig.from_toml(toml_file)

    # package_path et output_dir sont résolus relatifs au fichier toml
    assert cfg.package_path == tmp_path / "src"
    assert cfg.package_name == "mypkg"
    assert cfg.output_dir == tmp_path / "out"
    assert cfg.formats == ["mmd", "svg"]
    assert cfg.include_private is True
    assert cfg.public_only is True
    assert cfg.site_name == "Test Site"


def test_config_tool_gendoc_section(tmp_path: Path):
    toml_content = """
[tool.gendoc]
package_name = "toolpkg"
site_name = "From Tool"
"""

    toml_file = tmp_path / "pyproject.toml"
    toml_file.write_text(toml_content)

    cfg = GendocConfig.from_toml(toml_file)

    assert cfg.package_name == "toolpkg"
    assert cfg.site_name == "From Tool"


def test_config_merge_cli():
    cfg = GendocConfig()
    cfg.merge_cli(
        package_path=Path("my_pkg"),
        output_dir=Path("my_site"),
        exclude=["extra_test"],
        public_only=True,
        focus_class="MyClass",
        focus_depth=3,
    )

    assert cfg.package_path == Path("my_pkg")
    assert cfg.output_dir == Path("my_site")
    assert "extra_test" in cfg.exclude_patterns
    assert cfg.public_only is True
    assert cfg.focus_class == "MyClass"
    assert cfg.focus_depth == 3


def test_config_coerces_string_paths():
    """Les chemins passés en str sont convertis en Path (exemple du README)."""
    cfg = GendocConfig(package_path="src/mon_pkg", output_dir="site_x", docs_dir="docs_x")

    assert isinstance(cfg.package_path, Path)
    assert isinstance(cfg.output_dir, Path)
    assert isinstance(cfg.docs_dir, Path)


def test_build_docs_with_config_accepts_string_paths(temp_package, tmp_path: Path, monkeypatch):
    """build_docs_with_config fonctionne avec des chemins str, comme documenté."""
    import gendoc

    monkeypatch.chdir(tmp_path)
    cfg = GendocConfig(
        package_path=str(temp_package),
        output_dir="site_str",
        docs_dir="docs_str",
        package_name="testpkg",
    )
    docs = gendoc.build_docs_with_config(cfg)

    assert (docs / "index.md").exists()


def test_find_config_file(tmp_path: Path):
    # Créer gendoc.toml dans parent
    (tmp_path / "gendoc.toml").write_text('[gendoc]\npackage_name="found"\n')

    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)

    found = GendocConfig.find_config_file(sub)
    assert found is not None
    assert found.name == "gendoc.toml"


def test_load_config_no_file(tmp_path: Path):
    cfg = load_config(package_path=tmp_path)

    assert isinstance(cfg, GendocConfig)


def test_config_empty_lists_and_zero_override_defaults(tmp_path: Path):
    """[] et 0 sont des valeurs légitimes, pas des absences."""
    toml_file = tmp_path / "gendoc.toml"
    toml_file.write_text(
        "[gendoc]\nformats = []\nexclude_patterns = []\nfocus_depth = 0\n"
    )

    cfg = GendocConfig.from_toml(toml_file)

    assert cfg.formats == []
    assert cfg.exclude_patterns == []
    assert cfg.focus_depth == 0


def test_config_invalid_toml_friendly_error(tmp_path: Path):
    import pytest

    toml_file = tmp_path / "gendoc.toml"
    toml_file.write_text("[gendoc\npackage_path = ")

    with pytest.raises(ValueError, match="gendoc.toml"):
        GendocConfig.from_toml(toml_file)


def test_config_invalid_int_friendly_error(tmp_path: Path):
    import pytest

    toml_file = tmp_path / "gendoc.toml"
    toml_file.write_text('[gendoc]\nfocus_depth = "abc"\n')

    with pytest.raises(ValueError, match="focus_depth"):
        GendocConfig.from_toml(toml_file)


def test_load_config_missing_explicit_path_raises(tmp_path: Path):
    """Un --config pointant vers un fichier inexistant doit être une erreur, pas un silence."""
    import pytest

    with pytest.raises(FileNotFoundError):
        load_config(config_path=tmp_path / "nope.toml")


def test_config_enable_search_loaded(tmp_path: Path):
    toml_file = tmp_path / "gendoc.toml"
    toml_file.write_text("[gendoc]\nenable_search = false\n")

    cfg = GendocConfig.from_toml(toml_file)

    assert cfg.enable_search is False


def test_config_removed_dead_keys():
    """Les clés jamais implémentées ont été retirées du modèle de config."""
    cfg = GendocConfig()

    for dead in ("max_workers", "edit_uri", "enable_mermaid", "inheritance_depth"):
        assert not hasattr(cfg, dead), dead
