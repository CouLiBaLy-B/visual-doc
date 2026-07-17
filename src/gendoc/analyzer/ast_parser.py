"""Parseur AST : classes (y compris imbriquées), membres, fonctions et imports d'un module."""
from __future__ import annotations

import ast
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

from .models import AttributeInfo, ClassInfo, MethodInfo, get_visibility


def _annotation_to_str(node: ast.AST | None) -> str | None:
    """Convertit une annotation AST en string lisible."""
    if node is None:
        return None
    # Forward reference (x: "User") : restituer le contenu sans les quotes
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ast.unparse(node)


@dataclass
class ParsedModule:
    """Résultat complet du parsing d'un fichier, en une seule passe AST."""

    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[MethodInfo] = field(default_factory=list)
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)


def parse_module(file_path: Path, module_name: str) -> ParsedModule:
    """Parse un fichier Python : classes, fonctions top-level, docstring et imports.

    Raises:
        ValueError: fichier non décodable (encodage) ou non parsable (syntaxe).
    """
    try:
        # tokenize.open respecte le BOM et les déclarations d'encodage PEP 263,
        # et échoue explicitement au lieu de corrompre la source (errors="ignore").
        with tokenize.open(file_path) as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        raise ValueError(f"Erreur syntaxe dans {file_path}: {e}") from e
    except Exception as e:
        raise ValueError(f"Impossible de parser {file_path}: {e}") from e

    parsed = ParsedModule(docstring=ast.get_docstring(tree))
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            _collect_class(node, module_name, file_path, "", parsed.classes)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parsed.functions.append(_function_info(node))
    parsed.imports = _collect_imports(tree)
    return parsed


def parse_file_for_classes(file_path: Path, module_name: str) -> list[ClassInfo]:
    """Parse un fichier Python et extrait toutes les classes."""
    return parse_module(file_path, module_name).classes


def parse_module_imports(file_path: Path) -> list[str]:
    """Extrait les imports d'un module (dotted paths). Tolérant aux erreurs de parsing."""
    try:
        return parse_module(file_path, file_path.stem).imports
    except ValueError:
        return []


# Bases marquant une énumération et décorateurs marquant une dataclass
# (noms simples : `enum.Enum` et `dataclasses.dataclass` matchent par suffixe).
_ENUM_BASES = {"Enum", "StrEnum", "IntEnum", "IntFlag", "Flag"}
_DATACLASS_DECORATORS = {"dataclass"}


def _class_stereotype(node: ast.ClassDef) -> str | None:
    """Stéréotype UML de la classe : "enum", "dataclass" ou None."""
    for base in node.bases:
        base_name = (_annotation_to_str(base) or "").split(".")[-1]
        if base_name in _ENUM_BASES:
            return "enum"
    for dec in node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        dec_name = (_annotation_to_str(target) or "").split(".")[-1]
        if dec_name in _DATACLASS_DECORATORS:
            return "dataclass"
    return None


def _collect_class(
    node: ast.ClassDef,
    module_name: str,
    file_path: Path,
    prefix: str,
    out: list[ClassInfo],
) -> None:
    """Collecte une classe ; ses classes imbriquées sont émises séparément (`Outer.Inner`)."""
    local_name = f"{prefix}{node.name}"
    attributes: list[AttributeInfo] = []
    methods: list[MethodInfo] = []
    seen_attrs: set[str] = set()

    for stmt in node.body:
        if isinstance(stmt, ast.ClassDef):
            _collect_class(stmt, module_name, file_path, f"{local_name}.", out)
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.append(_function_info(stmt))
            if stmt.name == "__init__":
                _collect_init_attributes(stmt, attributes, seen_attrs)
        elif isinstance(stmt, ast.AnnAssign):
            _add_annassign_attr(stmt, attributes, seen_attrs, in_class_body=True)
        elif isinstance(stmt, ast.Assign):
            _add_assign_attrs(stmt, attributes, seen_attrs, in_class_body=True)

    bases = [b for b in (_annotation_to_str(base) for base in node.bases) if b]
    stereotype = _class_stereotype(node)

    if stereotype == "enum":
        # les membres d'enum sont des valeurs nommées, pas des attributs typés
        # (sinon RED = 1 serait rendu comme un attribut int)
        for attr in attributes:
            if attr.is_class_attribute:
                attr.type_annotation = None

    out.append(
        ClassInfo(
            name=local_name,
            module=module_name,
            file_path=file_path,
            bases=bases,
            attributes=attributes,
            methods=methods,
            docstring=ast.get_docstring(node),
            line_number=node.lineno,
            stereotype=stereotype,
        )
    )


def _collect_init_attributes(
    init_node: ast.FunctionDef | ast.AsyncFunctionDef,
    attributes: list[AttributeInfo],
    seen: set[str],
) -> None:
    """Trouve les `self.x = ...` de __init__ (y compris sous if/try/with/for),
    sans descendre dans les fonctions ou classes imbriquées."""
    stack: list[ast.stmt] = list(init_node.body)
    while stack:
        stmt = stack.pop(0)
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, ast.AnnAssign):
            _add_annassign_attr(stmt, attributes, seen, in_class_body=False)
        elif isinstance(stmt, ast.Assign):
            _add_assign_attrs(stmt, attributes, seen, in_class_body=False)
        for child_field in ("body", "orelse", "finalbody"):
            children = getattr(stmt, child_field, None)
            if children:
                stack.extend(children)
        for handler in getattr(stmt, "handlers", None) or []:
            stack.extend(handler.body)
        for case in getattr(stmt, "cases", None) or []:
            stack.extend(case.body)


def _add_annassign_attr(
    node: ast.AnnAssign,
    attributes: list[AttributeInfo],
    seen: set[str],
    *,
    in_class_body: bool,
) -> None:
    """Ajoute un attribut annoté (x: T = v en corps de classe, self.x: T = v dans __init__)."""
    target = node.target
    name: str | None = None
    if in_class_body:
        if isinstance(target, ast.Name):
            name = target.id
    else:
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            name = target.attr
    if not name or name in seen:
        return

    default = None
    if node.value is not None:
        try:
            default = ast.unparse(node.value)
        except Exception:
            default = "..."
    attributes.append(
        AttributeInfo(
            name=name,
            type_annotation=_annotation_to_str(node.annotation),
            default=default,
            visibility=get_visibility(name),
            is_class_attribute=in_class_body,
        )
    )
    seen.add(name)


def _add_assign_attrs(
    node: ast.Assign,
    attributes: list[AttributeInfo],
    seen: set[str],
    *,
    in_class_body: bool,
) -> None:
    """Ajoute les attributs d'une assignation simple (x = v ou self.x = v)."""
    for target in node.targets:
        name: str | None = None
        if in_class_body and isinstance(target, ast.Name):
            name = target.id
        elif (
            not in_class_body
            and isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
        ):
            name = target.attr
        if not name or name in seen:
            continue

        try:
            default = ast.unparse(node.value)
        except Exception:
            default = "..."
        attributes.append(
            AttributeInfo(
                name=name,
                type_annotation=_infer_type_from_value(node.value),
                default=default,
                visibility=get_visibility(name),
                is_class_attribute=in_class_body,
            )
        )
        seen.add(name)


def _function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> MethodInfo:
    """Construit un MethodInfo depuis un def/async def (méthode ou fonction de module)."""
    is_static = False
    is_classmethod = False
    is_property = False
    is_abstract = False
    for dec in node.decorator_list:
        dec_name = _annotation_to_str(dec) or ""
        if dec_name == "staticmethod":
            is_static = True
        elif dec_name == "classmethod":
            is_classmethod = True
        elif dec_name in ("property", "cached_property", "functools.cached_property"):
            is_property = True
        elif "abstractmethod" in dec_name:
            is_abstract = True

    params: list[tuple[str, str | None]] = []
    for arg in node.args.posonlyargs:
        params.append((arg.arg, _annotation_to_str(arg.annotation)))
    for arg in node.args.args:
        params.append((arg.arg, _annotation_to_str(arg.annotation)))
    if node.args.vararg:
        params.append((f"*{node.args.vararg.arg}", _annotation_to_str(node.args.vararg.annotation)))
    for arg in node.args.kwonlyargs:
        params.append((arg.arg, _annotation_to_str(arg.annotation)))
    if node.args.kwarg:
        params.append((f"**{node.args.kwarg.arg}", _annotation_to_str(node.args.kwarg.annotation)))

    defaults: dict[str, str] = {}
    positional = list(node.args.posonlyargs) + list(node.args.args)
    # les defaults s'alignent sur la fin des paramètres positionnels
    for arg, default_node in zip(reversed(positional), reversed(node.args.defaults), strict=False):
        try:
            defaults[arg.arg] = ast.unparse(default_node)
        except Exception:
            defaults[arg.arg] = "..."
    for arg, kw_default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        if kw_default is not None:
            try:
                defaults[arg.arg] = ast.unparse(kw_default)
            except Exception:
                defaults[arg.arg] = "..."

    return MethodInfo(
        name=node.name,
        parameters=params,
        return_type=_annotation_to_str(node.returns),
        visibility=get_visibility(node.name),
        is_static=is_static,
        is_classmethod=is_classmethod,
        is_property=is_property,
        is_abstract=is_abstract,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        defaults=defaults,
        docstring=ast.get_docstring(node),
    )


def _infer_type_from_value(value: ast.AST) -> str | None:
    """Infère un type depuis la valeur assignée : MyClass() -> MyClass, [] -> list, etc."""
    if isinstance(value, ast.Call):
        return _annotation_to_str(value.func)
    if isinstance(value, ast.List):
        return "list"
    if isinstance(value, ast.Dict):
        return "dict"
    if isinstance(value, ast.Set):
        return "set"
    if isinstance(value, ast.Constant):
        return type(value.value).__name__
    return None


def _collect_imports(tree: ast.Module) -> list[str]:
    """Extrait les imports du module (dotted paths ; les relatifs gardent leurs points)."""
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            level = node.level
            if node.module:
                imports.append("." * level + node.module)
            elif level > 0:
                # from . import X, Y : chaque nom importé est un sous-module potentiel
                imports.extend("." * level + alias.name for alias in node.names)
    return imports
