"""Tests CLI."""

from pathlib import Path

from click.testing import CliRunner

from gendoc.cli import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "gendoc" in result.output.lower()


def test_cli_build_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "--help"])

    assert result.exit_code == 0
    assert "package_path" in result.output.lower() or "package" in result.output.lower()


def test_cli_check_success(temp_package: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["check", str(temp_package)])

    assert result.exit_code == 0
    assert "analysable" in result.output.lower() or "modules" in result.output.lower()


def test_cli_check_failure(tmp_path: Path):
    bad_pkg = tmp_path / "badpkg"
    bad_pkg.mkdir()
    (bad_pkg / "__init__.py").write_text("")
    (bad_pkg / "bad.py").write_text("def foo(:\n syntax error\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["check", str(bad_pkg)])

    assert result.exit_code == 1
    assert "non analysable" in result.output.lower() or "erreur" in result.output.lower()


def test_cli_build(temp_package: Path, tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        import shutil

        # copier temp_package contenu dans cwd
        cwd = Path.cwd()
        pkg_dest = cwd / "testpkg"
        shutil.copytree(temp_package, pkg_dest)

        result = runner.invoke(
            cli,
            ["build", str(pkg_dest), "--output", str(cwd / "site"), "--no-build-site", "-v"],
        )

        # Vérifier exit_code 0
        assert result.exit_code == 0, f"CLI build failed: {result.output}"
        assert (cwd / "docs" / "index.md").exists()
        assert (cwd / "docs" / "diagrams" / "package.mmd").exists()


def test_cli_init(tmp_path: Path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert Path("gendoc.toml").exists()
        content = Path("gendoc.toml").read_text()
        assert "package_path" in content


def test_cli_build_respects_toml_package_path(temp_package: Path, tmp_path: Path):
    """Sans argument CLI, le package_path du gendoc.toml doit être utilisé."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cwd = Path.cwd()
        (cwd / "gendoc.toml").write_text(
            f'[gendoc]\npackage_path = "{temp_package}"\npackage_name = "testpkg"\n'
        )

        result = runner.invoke(cli, ["build", "--no-build-site"])

        assert result.exit_code == 0, result.output
        index = (cwd / "docs" / "index.md").read_text()
        assert "testpkg" in index


def test_cli_include_private_can_be_disabled(temp_package: Path, tmp_path: Path):
    """--no-include-private doit pouvoir surcharger include_private=true du TOML."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cwd = Path.cwd()
        (cwd / "gendoc.toml").write_text(
            f'[gendoc]\npackage_path = "{temp_package}"\npackage_name = "testpkg"\n'
            "include_private = true\n"
        )

        result = runner.invoke(cli, ["build", "--no-include-private", "--no-build-site", "-v"])

        assert result.exit_code == 0, result.output
        assert "include_private=False" in result.output


def test_cli_diagram(temp_package: Path, tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "diagrams_out"
    result = runner.invoke(cli, ["diagram", str(temp_package), "--output", str(out)])

    assert result.exit_code == 0
    assert (out / "package.mmd").exists()
    assert (out / "classes.mmd").exists()


def test_cli_diagram_single_format(temp_package: Path, tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "diagrams_puml"
    result = runner.invoke(
        cli, ["diagram", str(temp_package), "--output", str(out), "--format", "plantuml"]
    )

    assert result.exit_code == 0
    assert (out / "package.puml").exists()
    assert not (out / "package.mmd").exists()


def test_cli_build_without_mkdocs_mentions_site_extra(temp_package: Path, tmp_path: Path):
    """Le message d'installation doit afficher l'extra [site] (non avalé par Rich)."""
    from unittest.mock import patch

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch("importlib.util.find_spec", return_value=None):
            result = runner.invoke(cli, ["build", str(temp_package)])

        assert result.exit_code == 0, result.output
        assert "gendoc[site]" in result.output.replace("\n", "")


def test_cli_serve_builds_docs_and_launches_mkdocs(temp_package: Path, tmp_path: Path):
    """gendoc serve régénère les docs puis lance mkdocs serve."""
    from unittest.mock import MagicMock, patch

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cwd = Path.cwd()
        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            result = runner.invoke(cli, ["serve", str(temp_package), "--port", "8123"])

        assert result.exit_code == 0, result.output
        assert (cwd / "docs" / "index.md").exists()
        cmd = [str(part) for part in mock_run.call_args[0][0]]
        assert "mkdocs" in cmd
        assert "serve" in cmd
        assert "127.0.0.1:8123" in cmd


def test_cli_serve_without_mkdocs_fails_with_hint(temp_package: Path, tmp_path: Path):
    from unittest.mock import patch

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with patch("importlib.util.find_spec", return_value=None):
            result = runner.invoke(cli, ["serve", str(temp_package)])

        assert result.exit_code == 1
        assert "gendoc[site]" in result.output.replace("\n", "")


def test_cli_build_focus_and_formats(temp_package: Path, tmp_path: Path):
    """--focus génère la page focus ; --formats mmd n'écrit aucun SVG."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cwd = Path.cwd()
        result = runner.invoke(
            cli,
            [
                "build",
                str(temp_package),
                "--focus",
                "User",
                "--depth",
                "1",
                "--formats",
                "mmd",
                "--no-build-site",
            ],
        )

        assert result.exit_code == 0, result.output
        assert (cwd / "docs" / "focus.md").exists()
        assert (cwd / "docs" / "diagrams" / "focus_User.mmd").exists()
        assert not list((cwd / "docs" / "diagrams").glob("*.svg"))
