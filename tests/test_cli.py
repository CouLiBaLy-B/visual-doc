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
    with runner.isolated_filesystem(temp_dir=tmp_path) as td:
        # td est un Path temporaire ? isolated_filesystem donne string path mais context
        # On est déjà dans temp, utilisons temp_package qui est hors de ce filesystem
        # Donc besoin de recréer package dans isolated fs
        # Simplifions: on teste via invoke direct avec output dans tmp_path
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


def test_cli_diagram(temp_package: Path, tmp_path: Path):
    runner = CliRunner()
    out = tmp_path / "diagrams_out"
    result = runner.invoke(cli, ["diagram", str(temp_package), "--output", str(out)])

    assert result.exit_code == 0
    assert (out / "package.mmd").exists()
    assert (out / "classes.mmd").exists()
