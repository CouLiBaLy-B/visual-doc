"""Parseur AST pour extraire classes, attributs, méthodes."""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Optional

from .models import AttributeInfo, ClassInfo, MethodInfo, Visibility, get_visibility


def _annotation_to_str(node: ast.AST | None) -> Optional[str]:
    """Convertit une annotation AST en string."""
    if node is None:
        return None
    try:
        # Python 3.9+: ast.unparse
        return ast.unparse(node)
    except AttributeError:  # pragma: no cover - Python <3.9 fallback
        # Fallback pour anciennes versions, implémentation simplifiée
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{_annotation_to_str(node.value)}.{node.attr}"
        if isinstance(node, ast.Subscript):
            value = _annotation_to_str(node.value)
            slice_str = _annotation_to_str(node.slice)
            return f"{value}[{slice_str}]"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        if isinstance(node, ast.Tuple):
            return ", ".join(_annotation_to_str(e) or "" for e in node.elts)
        if isinstance(node, ast.List):
            return f"[{', '.join(_annotation_to_str(e) or '' for e in node.elts)}]"
        return None  # pragma: no cover


def _get_docstring(node: ast.AST) -> Optional[str]:
    """Extrait docstring d'un noeud."""
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    return ast.get_docstring(node)


class ClassVisitor(ast.NodeVisitor):
    """Visiteur pour extraire infos d'une classe."""

    def __init__(self) -> None:
        self.attributes: list[AttributeInfo] = []
        self.methods: list[MethodInfo] = []
        self._seen_attrs: set[str] = set()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # attribut typé: x: int = 1 ou x: int
        target = node.target
        name: Optional[str] = None
        is_class_attr = False

        if isinstance(target, ast.Name):
            name = target.id
        elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id == "self":
                name = target.attr
            else:
                # attribut de classe via ClassName.attr ? ignorer pour now
                name = target.attr
                is_class_attr = True

        if name and name not in self._seen_attrs:
            type_ann = _annotation_to_str(node.annotation)
            default = None
            if node.value:
                try:
                    default = ast.unparse(node.value)
                except Exception:
                    default = "..."
            self.attributes.append(
                AttributeInfo(
                    name=name,
                    type_annotation=type_ann,
                    default=default,
                    visibility=get_visibility(name),
                    is_class_attribute=is_class_attr or self._is_in_class_body(),
                )
            )
            self._seen_attrs.add(name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # attribut assigné dans __init__ ou corps de classe
        for target in node.targets:
            name: Optional[str] = None
            is_class_attr = False
            if isinstance(target, ast.Name):
                name = target.id
                is_class_attr = self._is_in_class_body()
            elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                if target.value.id == "self":
                    name = target.attr
                else:
                    continue

            if name and name not in self._seen_attrs:
                # tenter d'inférer type depuis valeur
                type_ann = self._infer_type_from_value(node.value)
                default = None
                try:
                    default = ast.unparse(node.value)
                except Exception:
                    default = "..."
                # si dans __init__, c'est instance attribute
                # si dans corps de classe direct, class attribute
                self.attributes.append(
                    AttributeInfo(
                        name=name,
                        type_annotation=type_ann,
                        default=default,
                        visibility=get_visibility(name),
                        is_class_attribute=is_class_attr,
                    )
                )
                self._seen_attrs.add(name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node)
        # Ne pas visiter les fonctions imbriquées comme méthodes
        # self.generic_visit(node) serait trop profond, on skip le corps pour éviter double comptage ?
        # Mais on veut attributs dans __init__, donc on doit visiter __init__ body
        if node.name == "__init__":
            # Visiter uniquement le corps de __init__ pour trouver self.x = ...
            for stmt in node.body:
                self.visit(stmt)
        # Pour autres méthodes, ne pas descendre pour éviter confondre variables locales avec attributs

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node)  # type: ignore[arg-type]

    def _process_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        # Détecter décorateurs
        is_static = False
        is_classmethod = False
        is_property = False
        is_abstract = False
        for dec in node.decorator_list:
            dec_name = _annotation_to_str(dec)
            if dec_name in ("staticmethod",):
                is_static = True
            elif dec_name in ("classmethod",):
                is_classmethod = True
            elif dec_name in ("property",):
                is_property = True
            elif dec_name and "abstractmethod" in dec_name:
                is_abstract = True

        # Paramètres
        params: list[tuple[str, Optional[str]]] = []
        for arg in node.args.args:
            ann = _annotation_to_str(arg.annotation)
            params.append((arg.arg, ann))
        # vararg, kwonly, etc.
        if node.args.vararg:
            ann = _annotation_to_str(node.args.vararg.annotation)
            params.append((f"*{node.args.vararg.arg}", ann))
        for kwarg in node.args.kwonlyargs:
            ann = _annotation_to_str(kwarg.annotation)
            params.append((kwarg.arg, ann))
        if node.args.kwarg:
            ann = _annotation_to_str(node.args.kwarg.annotation)
            params.append((f"**{node.args.kwarg.arg}", ann))

        return_type = _annotation_to_str(node.returns)
        doc = _get_docstring(node)

        self.methods.append(
            MethodInfo(
                name=node.name,
                parameters=params,
                return_type=return_type,
                visibility=get_visibility(node.name),
                is_static=is_static,
                is_classmethod=is_classmethod,
                is_property=is_property,
                is_abstract=is_abstract,
                docstring=doc,
            )
        )

    def _infer_type_from_value(self, value: ast.AST) -> Optional[str]:
        # Inférer type depuis instantiation: MyClass() -> MyClass, [] -> list, {} -> dict
        if isinstance(value, ast.Call):
            t = _annotation_to_str(value.func)
            return t
        if isinstance(value, ast.List):
            return "list"
        if isinstance(value, ast.Dict):
            return "dict"
        if isinstance(value, ast.Set):
            return "set"
        if isinstance(value, ast.Constant):
            return type(value.value).__name__
        return None

    def _is_in_class_body(self) -> bool:
        # Simplification: on considère que si on est dans visit direct, on est dans corps de classe
        # Pour distinguer __init__, on utilise logique externe
        return True


def parse_file_for_classes(file_path: Path, module_name: str) -> list[ClassInfo]:
    """Parse un fichier Python et extrait toutes les classes."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        raise ValueError(f"Erreur syntaxe dans {file_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Impossible de parser {file_path}: {e}") from e

    classes: list[ClassInfo] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            visitor = ClassVisitor()
            # Extraire bases
            bases: list[str] = []
            for base in node.bases:
                base_str = _annotation_to_str(base)
                if base_str:
                    bases.append(base_str)

            # Visiter corps pour attributs/méthodes
            # Re-parse corps
            # Le visitor gère déjà FunctionDef etc.
            for stmt in node.body:
                visitor.visit(stmt)

            # Aussi chercher les attributs définis via AnnAssign au niveau classe directement
            # Le visitor a déjà fait

            doc = _get_docstring(node)

            cls_info = ClassInfo(
                name=node.name,
                module=module_name,
                file_path=file_path,
                bases=bases,
                attributes=visitor.attributes,
                methods=visitor.methods,
                docstring=doc,
                line_number=node.lineno,
            )
            classes.append(cls_info)

    return classes


def parse_module_imports(file_path: Path) -> list[str]:
    """Extrait les imports d'un module (dotted paths)."""
    try:
        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            level = node.level
            module = node.module or ""
            # Cas: from . import X, Y  -> module vide mais level >0
            if module:
                if level > 0:
                    imports.append("." * level + module)
                else:
                    imports.append(module)
                # aussi, si on importe depuis .models par ex, on a déjà le module,
                # mais pour être plus précis on pourrait considérer les noms importés
                # comme sous-modules potentiels si ce sont des modules?
                # On ajoute les noms importés comme imports relatifs
                # si from . import circular_b -> on veut "circular_b"
                # On traite ci-dessous
            # Pour from . import X
            if level > 0:
                for alias in node.names:
                    # alias.name est le nom importé (ex: circular_b)
                    # Construire import relatif vers ce nom
                    if module:
                        # from .module import X -> on a déjà module, mais on peut aussi considérer submodule
                        # on garde module déjà ajouté
                        pass
                    else:
                        # from . import X => import relatif ".X" ou juste "X"
                        # On ajoute ".X" et "X" pour heuristique
                        imports.append("." * level + alias.name)
                        imports.append(alias.name)
            else:
                # import absolu avec module vide? rare
                pass
    return imports
