"""Configuration via gendoc.toml + CLI override."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GendocConfig:
    """Configuration de gendoc."""

    # Entrée
    package_path: Path = Path(".")
    package_name: str | None = None

    # Sortie
    output_dir: Path = Path("site")
    docs_dir: Path = Path("docs")
    formats: list[str] = field(default_factory=lambda: ["mmd", "puml", "svg"])

    # Filtrage
    exclude_patterns: list[str] = field(
        default_factory=lambda: ["test_*", "*_test.py", "tests", "__pycache__"]
    )
    include_private: bool = False
    include_tests: bool = False
    public_only: bool = False

    # Diagrammes ciblés
    focus_class: str | None = None
    focus_depth: int = 2

    # Site
    site_name: str = "Documentation"
    theme: str = "material"
    enable_search: bool = True

    # MkDocs extras
    repo_url: str | None = None

    def __post_init__(self) -> None:
        # Accepter des str pour les chemins (usage librairie documenté dans le README)
        self.package_path = Path(self.package_path)
        self.output_dir = Path(self.output_dir)
        self.docs_dir = Path(self.docs_dir)

    @classmethod
    def from_toml(cls, toml_path: Path) -> GendocConfig:
        """Charge config depuis fichier TOML.

        Raises:
            ValueError: TOML mal formé ou valeur du mauvais type, avec le
                fichier et la clé en cause dans le message.
        """
        if not toml_path.exists():
            return cls()

        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"TOML invalide dans {toml_path}: {e}") from e

        # Supporter [tool.gendoc] et [gendoc]
        cfg_data: dict[str, Any]
        if "tool" in data and "gendoc" in data["tool"]:
            cfg_data = data["tool"]["gendoc"]
        elif "gendoc" in data:
            cfg_data = data["gendoc"]
        else:
            cfg_data = data

        instance = cls()
        config_dir = toml_path.parent

        def resolve_path(value: str | Path) -> Path:
            p = Path(value)
            if p.is_absolute():
                return p
            # relatif au dossier du fichier toml
            return (config_dir / p).resolve()

        def get(key: str) -> Any:
            return cfg_data.get(key)

        def get_int(key: str) -> int | None:
            value = get(key)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"Valeur invalide pour '{key}' dans {toml_path}: {value!r} (entier attendu)"
                ) from e

        if get("package_path") is not None:
            instance.package_path = resolve_path(get("package_path"))
        if get("package_name") is not None:
            instance.package_name = get("package_name")
        if get("output_dir") is not None:
            instance.output_dir = resolve_path(get("output_dir"))
        if get("docs_dir") is not None:
            instance.docs_dir = resolve_path(get("docs_dir"))
        if get("formats") is not None:
            instance.formats = list(get("formats"))
        if get("exclude_patterns") is not None:
            instance.exclude_patterns = list(get("exclude_patterns"))
        if get("include_private") is not None:
            instance.include_private = bool(get("include_private"))
        if get("include_tests") is not None:
            instance.include_tests = bool(get("include_tests"))
        if get("public_only") is not None:
            instance.public_only = bool(get("public_only"))
        if get("focus_class") is not None:
            instance.focus_class = get("focus_class")
        focus_depth = get_int("focus_depth")
        if focus_depth is not None:
            instance.focus_depth = focus_depth
        if get("site_name") is not None:
            instance.site_name = get("site_name")
        if get("theme") is not None:
            instance.theme = get("theme")
        if get("enable_search") is not None:
            instance.enable_search = bool(get("enable_search"))
        if get("repo_url") is not None:
            instance.repo_url = get("repo_url")

        return instance

    def merge_cli(
        self,
        package_path: Path | None = None,
        output_dir: Path | None = None,
        exclude: list[str] | None = None,
        include_private: bool | None = None,
        public_only: bool | None = None,
        formats: list[str] | None = None,
        focus_class: str | None = None,
        focus_depth: int | None = None,
        site_name: str | None = None,
    ) -> GendocConfig:
        """Fusionne overrides CLI (CLI a priorité)."""
        if package_path:
            self.package_path = package_path
        if output_dir:
            self.output_dir = output_dir
        if exclude:
            # dict.fromkeys : dédoublonnage déterministe, ordre d'apparition conservé
            self.exclude_patterns = list(dict.fromkeys(self.exclude_patterns + exclude))
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
    def find_config_file(cls, start_path: Path) -> Path | None:
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
    config_path: Path | None = None,
    package_path: Path | None = None,
) -> GendocConfig:
    """Charge config avec recherche automatique.

    Raises:
        FileNotFoundError: si un config_path explicite est fourni mais absent
            (une faute de frappe ne doit pas être ignorée en silence).
    """

    if config_path is not None:
        if not config_path.exists():
            raise FileNotFoundError(f"Fichier de configuration introuvable: {config_path}")
        return GendocConfig.from_toml(config_path)

    # Chercher auto
    search_start = package_path or Path.cwd()
    found = GendocConfig.find_config_file(search_start)
    if found:
        return GendocConfig.from_toml(found)

    return GendocConfig()
