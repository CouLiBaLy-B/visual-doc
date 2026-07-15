"""Tests supplémentaires pour améliorer couverture."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from gendoc.analyzer import ast_parser, package_analyzer
from gendoc.analyzer.models import Visibility, get_visibility
from gendoc.cli import cli
from gendoc.renderers import svg


def test_visibility_detection():
    assert get_visibility("public") == Visibility.PUBLIC
    assert get_visibility("_protected") == Visibility.PROTECTED
    assert get_visibility("__private") == Visibility.PRIVATE
    assert get_visibility("__dunder__") == Visibility.DUNDER


def test_annotation_to_str():
    import ast

    node = ast.parse("x: int").body[0].annotation  # type: ignore
    result = ast_parser._annotation_to_str(node)
    assert result == "int"

    assert ast_parser._annotation_to_str(None) is None


def test_function_docstring_extracted(tmp_path: Path):
    code = '''
def foo():
    """Docstring test."""
    pass
'''
    f = tmp_path / "mod.py"
    f.write_text(code)
    parsed = ast_parser.parse_module(f, "mod")
    assert parsed.functions[0].docstring == "Docstring test."


def test_infer_type_from_value():
    import ast

    # List
    node = ast.parse("x = []").body[0].value
    assert ast_parser._infer_type_from_value(node) == "list"
    # Dict
    node = ast.parse("x = {}").body[0].value
    assert ast_parser._infer_type_from_value(node) == "dict"
    # Constant
    node = ast.parse("x = 5").body[0].value
    assert ast_parser._infer_type_from_value(node) == "int"
    # Call
    node = ast.parse("x = MyClass()").body[0].value
    assert ast_parser._infer_type_from_value(node) == "MyClass"


def test_cli_build_with_mkdocs_mock(temp_package: Path, tmp_path: Path):
    """Test build avec build_site True mais mock subprocess."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import shutil

        cwd = Path.cwd()
        pkg_dest = cwd / "testpkg"
        shutil.copytree(temp_package, pkg_dest)

        # Créer docs dir pour que builder fonctionne
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_result.stdout = "Mocked build"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = runner.invoke(
                cli,
                ["build", str(pkg_dest), "--output", str(cwd / "site"), "-v"],
            )
            assert result.exit_code == 0
            # Vérifier que subprocess.run appelé
            assert mock_run.called or (cwd / "docs" / "index.md").exists()


def test_cli_build_mkdocs_failure_mock(temp_package: Path, tmp_path: Path):
    """Test build où mkdocs échoue."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import shutil

        cwd = Path.cwd()
        pkg_dest = cwd / "testpkg"
        shutil.copytree(temp_package, pkg_dest)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = runner.invoke(
                cli,
                ["build", str(pkg_dest), "--output", str(cwd / "site"), "-v"],
            )
            assert result.exit_code == 0  # ne doit pas échouer, warning seulement


def test_svg_save_and_convert(tmp_path: Path):
    svg_content = "<svg><text>test</text></svg>"
    svg_path = tmp_path / "test.svg"
    png_path = tmp_path / "test.png"

    svg.save_svg(svg_content, svg_path)
    assert svg_path.exists()

    # Conversion peut échouer si cairosvg pas installé, mais ne doit pas crasher
    result = svg.try_convert_svg_to_png(svg_path, png_path)
    assert isinstance(result, bool)
    if result:
        assert png_path.exists()


def test_package_analyzer_helpers():
    from pathlib import Path

    # Test get_module_dotted_path
    root = Path("/tmp/pkg")
    file = root / "sub" / "models.py"
    dotted = package_analyzer.get_module_dotted_path(file, root, "pkg")
    assert dotted == "pkg.sub.models"

    file2 = root / "__init__.py"
    dotted2 = package_analyzer.get_module_dotted_path(file2, root, "pkg")
    assert dotted2 == "pkg"


def test_relationship_extract_types():
    from gendoc.analyzer.relationships import _extract_types_from_annotation

    types = _extract_types_from_annotation("Optional[List[MyClass]]")
    assert "MyClass" in types
    assert "Optional" not in types
    assert "List" not in types


def test_config_find_no_file(tmp_path: Path):
    from gendoc.config import GendocConfig

    # Dans dossier vide, pas de config
    found = GendocConfig.find_config_file(tmp_path)
    assert found is None


def test_cli_init_exists(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path("gendoc.toml").write_text("[gendoc]\n")
        # Tester avec confirmation No
        result = runner.invoke(cli, ["init"], input="n\n")
        assert result.exit_code == 0
        # Tester avec Yes
        result = runner.invoke(cli, ["init"], input="y\n")
        assert result.exit_code == 0
        assert Path("gendoc.toml").exists()
