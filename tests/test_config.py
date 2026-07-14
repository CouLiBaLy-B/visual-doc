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
