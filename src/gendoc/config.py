"""Configuration via gendoc.toml + CLI override."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore


@dataclass
class GendocConfig:
    """Configuration de gendoc."""

    # Entrée
    package_path: Path = Path(".")
    package_name: Optional[str] = None

    # Sortie
    output_dir: Path = Path("site")
    docs_dir: Path = Path("docs")
    formats: list[str] = field(default_factory=lambda: ["mmd", "puml", "svg"])

    # Filtrage
    exclude_patterns: list[str] = field(default_factory=lambda: ["test_*", "*_test.py", "tests", "__pycache__"])
    include_private: bool = False
    include_tests: bool = False
    public_only: bool = False
    inheritance_depth: Optional[int] = None

    # Diagrammes ciblés
    focus_class: Optional[str] = None
    focus_depth: int = 2

    # Site
    site_name: str = "Documentation"
    theme: str = "material"
    enable_mermaid: bool = True
    enable_search: bool = True

    # Performance
    max_workers: int = 4

    # MkDocs extras
    repo_url: Optional[str] = None
    edit_uri: Optional[str] = None

    @classmethod
    def from_toml(cls, toml_path: Path) -> "GendocConfig":
        """Charge config depuis fichier TOML."""
        if not toml_path.exists():
            return cls()

        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))

        # Supporter [tool.gendoc] et [gendoc]
        cfg_data: dict[str, Any] = {}
        if "tool" in data and "gendoc" in data["tool"]:
            cfg_data = data["tool"]["gendoc"]
        elif "gendoc" in data:
            cfg_data = data["gendoc"]
        else:
            cfg_data = data

        # Mapper vers dataclass
        instance = cls()
        # Garder trace du fichier config pour résolution relative
        config_dir = toml_path.parent

        # Helper pour résoudre chemins relatifs au fichier config
        def resolve_path(value: str | Path) -> Path:
            p = Path(value)
            if p.is_absolute():
                return p
            # relatif au dossier du fichier toml
            return (config_dir / p).resolve()

        # Helper
        def get(key: str, default: Any = None) -> Any:
            return cfg_data.get(key, default)

        if get("package_path"):
            instance.package_path = resolve_path(get("package_path"))
        if get("package_name"):
            instance.package_name = get("package_name")
        if get("output_dir"):
            instance.output_dir = resolve_path(get("output_dir"))
        if get("docs_dir"):
            instance.docs_dir = resolve_path(get("docs_dir"))
        if get("formats"):
            instance.formats = get("formats")
        if get("exclude_patterns"):
            instance.exclude_patterns = get("exclude_patterns")
        if get("include_private") is not None:
            instance.include_private = bool(get("include_private"))
        if get("include_tests") is not None:
            instance.include_tests = bool(get("include_tests"))
        if get("public_only") is not None:
            instance.public_only = bool(get("public_only"))
        if get("inheritance_depth") is not None:
            instance.inheritance_depth = int(get("inheritance_depth"))
        if get("focus_class"):
            instance.focus_class = get("focus_class")
        if get("focus_depth"):
            instance.focus_depth = int(get("focus_depth"))
        if get("site_name"):
            instance.site_name = get("site_name")
        if get("theme"):
            instance.theme = get("theme")
        if get("enable_mermaid") is not None:
            instance.enable_mermaid = bool(get("enable_mermaid"))
        if get("repo_url"):
            instance.repo_url = get("repo_url")

        return instance

    def merge_cli(
        self,
        package_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        exclude: Optional[list[str]] = None,
        include_private: Optional[bool] = None,
        public_only: Optional[bool] = None,
        formats: Optional[list[str]] = None,
        focus_class: Optional[str] = None,
        focus_depth: Optional[int] = None,
        site_name: Optional[str] = None,
    ) -> "GendocConfig":
        """Fusionne overrides CLI (CLI a priorité)."""
        if package_path:
            self.package_path = package_path
        if output_dir:
            self.output_dir = output_dir
        if exclude:
            self.exclude_patterns = list(set(self.exclude_patterns + exclude))
        if include_private is not None:
            self.include_private = include_private
        if public_only is not None:
            self.public_only = public_only
        if formats:
            self.formats = formats
        if focus_class:
            self.focus_class = focus_class
        if focus_depth is not None:
            self.focus_depth = focus_depth
        if site_name:
            self.site_name = site_name
        return self

    @classmethod
    def find_config_file(cls, start_path: Path) -> Optional[Path]:
        """Cherche gendoc.toml en remontant l'arbre."""
        current = start_path.resolve()
        if current.is_file():
            current = current.parent

        for _ in range(10):  # max 10 niveaux
            for name in ["gendoc.toml", ".gendoc.toml", "pyproject.toml"]:
                candidate = current / name
                if candidate.exists():
                    # vérifier si contient section gendoc pour pyproject.toml
                    if name == "pyproject.toml":
                        try:
                            data = tomllib.loads(candidate.read_text(encoding="utf-8"))
                            if "tool" in data and "gendoc" in data["tool"]:
                                return candidate
                        except Exception:
                            continue
                    else:
                        return candidate
            if current.parent == current:
                break
            current = current.parent
        return None


def load_config(
    config_path: Optional[Path] = None,
    package_path: Optional[Path] = None,
) -> GendocConfig:
    """Charge config avec recherche automatique."""

    if config_path and config_path.exists():
        return GendocConfig.from_toml(config_path)

    # Chercher auto
    search_start = package_path or Path.cwd()
    found = GendocConfig.find_config_file(search_start)
    if found:
        return GendocConfig.from_toml(found)

    return GendocConfig()
