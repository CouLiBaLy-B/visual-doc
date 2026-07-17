"""Tests du cache de parsing incrémental."""

from pathlib import Path

from gendoc.analyzer import analyze_package, package_analyzer


def _spy_parse_module(monkeypatch) -> list[Path]:
    """Trace les fichiers réellement re-parsés par analyze_package."""
    calls: list[Path] = []
    real = package_analyzer.parse_module

    def spy(file_path: Path, module_name: str):
        calls.append(file_path)
        return real(file_path, module_name)

    monkeypatch.setattr(package_analyzer, "parse_module", spy)
    return calls


def test_second_run_skips_unchanged_files(temp_package, tmp_path: Path, monkeypatch):
    """Au 2e run, aucun fichier inchangé n'est re-parsé."""
    cache_dir = tmp_path / "cache"
    analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    calls = _spy_parse_module(monkeypatch)
    pkg = analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    assert calls == []
    assert "testpkg.models" in pkg.modules  # le résultat vient bien du cache


def test_modified_file_is_reparsed_alone(temp_package, tmp_path: Path, monkeypatch):
    """Modifier un seul fichier ne re-parse que celui-là, et le résultat le reflète."""
    cache_dir = tmp_path / "cache"
    analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    services = temp_package / "services.py"
    services.write_text(services.read_text() + "\n\nclass Extra:\n    pass\n")

    calls = _spy_parse_module(monkeypatch)
    pkg = analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    assert calls == [services]
    assert "testpkg.services.Extra" in pkg.classes


def test_cached_analysis_identical_to_cold(temp_package, tmp_path: Path):
    """Le résultat avec cache (chaud) est identique à une analyse à froid."""
    cache_dir = tmp_path / "cache"
    cold = analyze_package(temp_package, package_name="testpkg")
    analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)
    warm = analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    assert set(warm.modules) == set(cold.modules)
    assert set(warm.classes) == set(cold.classes)
    assert {(r.source, r.target, r.relation_type) for r in warm.relations} == {
        (r.source, r.target, r.relation_type) for r in cold.relations
    }
    assert warm.dependencies == cold.dependencies
    assert warm.circular_dependencies == cold.circular_dependencies

    m_cold = cold.classes["testpkg.models.Order"]
    m_warm = warm.classes["testpkg.models.Order"]
    assert [a.__dict__ for a in m_warm.attributes] == [a.__dict__ for a in m_cold.attributes]
    assert [m.__dict__ for m in m_warm.methods] == [m.__dict__ for m in m_cold.methods]


def test_corrupted_cache_entry_falls_back_to_parse(temp_package, tmp_path: Path):
    """Une entrée corrompue est ignorée : re-parse, jamais de crash."""
    cache_dir = tmp_path / "cache"
    analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    for entry in cache_dir.glob("*.json"):
        entry.write_text("{corrompu")

    pkg = analyze_package(temp_package, package_name="testpkg", cache_dir=cache_dir)

    assert pkg.errors == []
    assert "testpkg.models" in pkg.modules
