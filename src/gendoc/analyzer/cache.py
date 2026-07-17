"""Cache disque du parsing AST : les fichiers inchangés ne sont pas re-parsés.

Une entrée par fichier source, invalidée par hash du contenu (sha256),
version de gendoc et version du format de cache. Toute entrée illisible ou
périmée est ignorée silencieusement (le fichier est alors re-parsé) : le
cache ne peut jamais rendre un résultat différent d'une analyse à froid.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .. import __version__
from .ast_parser import ParsedModule
from .models import AttributeInfo, ClassInfo, MethodInfo, Visibility

logger = logging.getLogger(__name__)

# À incrémenter à chaque changement de schéma des modèles sérialisés.
_CACHE_FORMAT = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _attribute_from_dict(d: dict) -> AttributeInfo:
    return AttributeInfo(
        name=d["name"],
        type_annotation=d["type_annotation"],
        default=d["default"],
        visibility=Visibility(d["visibility"]),
        is_class_attribute=d["is_class_attribute"],
    )


def _method_from_dict(d: dict) -> MethodInfo:
    return MethodInfo(
        name=d["name"],
        parameters=[(n, t) for n, t in d["parameters"]],
        return_type=d["return_type"],
        visibility=Visibility(d["visibility"]),
        is_static=d["is_static"],
        is_classmethod=d["is_classmethod"],
        is_property=d["is_property"],
        is_abstract=d["is_abstract"],
        is_async=d["is_async"],
        defaults=d["defaults"],
        docstring=d["docstring"],
    )


def _class_from_dict(d: dict) -> ClassInfo:
    return ClassInfo(
        name=d["name"],
        module=d["module"],
        file_path=Path(d["file_path"]),
        bases=d["bases"],
        attributes=[_attribute_from_dict(a) for a in d["attributes"]],
        methods=[_method_from_dict(m) for m in d["methods"]],
        docstring=d["docstring"],
        line_number=d["line_number"],
        stereotype=d["stereotype"],
    )


class ParseCache:
    """Cache clé/valeur sur disque pour les résultats de ``parse_module``."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir

    def _entry_path(self, file_path: Path, module_name: str) -> Path:
        key = _sha256(f"{file_path.resolve()}::{module_name}".encode())
        return self.cache_dir / f"{key}.json"

    def get(self, file_path: Path, module_name: str, source: bytes) -> ParsedModule | None:
        """Retourne le ParsedModule en cache si l'entrée est valide, sinon None."""
        entry = self._entry_path(file_path, module_name)
        try:
            payload = json.loads(entry.read_text(encoding="utf-8"))
            if (
                payload["format"] != _CACHE_FORMAT
                or payload["gendoc"] != __version__
                or payload["sha256"] != _sha256(source)
            ):
                return None
            data = payload["data"]
            return ParsedModule(
                classes=[_class_from_dict(c) for c in data["classes"]],
                functions=[_method_from_dict(f) for f in data["functions"]],
                docstring=data["docstring"],
                imports=data["imports"],
            )
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.debug("entrée de cache illisible pour %s (%s), re-parse", file_path, e)
            return None

    def put(self, file_path: Path, module_name: str, source: bytes, parsed: ParsedModule) -> None:
        """Écrit l'entrée de cache ; une erreur d'écriture n'interrompt jamais l'analyse."""
        entry = self._entry_path(file_path, module_name)
        payload = {
            "format": _CACHE_FORMAT,
            "gendoc": __version__,
            "sha256": _sha256(source),
            "data": {
                "classes": [asdict(c) for c in parsed.classes],
                "functions": [asdict(f) for f in parsed.functions],
                "docstring": parsed.docstring,
                "imports": parsed.imports,
            },
        }
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            entry.write_text(json.dumps(payload, default=str), encoding="utf-8")
        except OSError as e:
            logger.debug("écriture du cache impossible dans %s: %s", entry, e)
