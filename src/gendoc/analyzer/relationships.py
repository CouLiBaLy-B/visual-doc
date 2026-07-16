"""Détection des relations entre classes et des cycles de dépendances."""
from __future__ import annotations

import ast
import re
from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ClassInfo

from .models import RelationInfo, RelationType

# Noms de types à ignorer lors de l'extraction (builtins + typing)
_IGNORED_TYPE_NAMES = {
    "Optional", "Union", "Any", "None", "Self", "ClassVar", "Final", "Literal",
    "Annotated", "Type", "type", "object",
    "str", "int", "float", "bool", "bytes", "bytearray", "complex",
    "list", "dict", "set", "tuple", "frozenset",
    "List", "Dict", "Set", "Tuple", "FrozenSet",
    "Callable", "Iterable", "Iterator", "Sequence", "Mapping", "MutableMapping",
    "MutableSequence", "Collection", "Generator", "Awaitable", "Coroutine",
    "typing", "collections", "abc",
}

# Types conteneurs : un type projet dans leur subscript = agrégation
_COLLECTION_TYPES = {
    "list", "List", "set", "Set", "frozenset", "FrozenSet", "tuple", "Tuple",
    "dict", "Dict", "Mapping", "MutableMapping", "defaultdict", "OrderedDict",
    "Sequence", "MutableSequence", "Collection", "Iterable", "deque",
}


def _node_simple_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _classify_annotation_types(annotation: str) -> dict[str, bool]:
    """Extrait les noms de types d'une annotation via l'AST.

    Returns:
        dict {nom de type: True si le nom apparaît dans un conteneur (list[X], ...)}.
    """
    try:
        tree = ast.parse(annotation, mode="eval")
    except SyntaxError:
        # annotation non parsable : fallback regex, sans info de conteneur
        tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
        return dict.fromkeys(tokens, False)

    result: dict[str, bool] = {}

    def visit(node: ast.AST, in_collection: bool) -> None:
        if isinstance(node, ast.Subscript):
            base_name = _node_simple_name(node.value)
            visit(node.value, in_collection)
            visit(node.slice, in_collection or base_name in _COLLECTION_TYPES)
        elif isinstance(node, ast.Name):
            result[node.id] = result.get(node.id, False) or in_collection
        elif isinstance(node, ast.Attribute):
            result[node.attr] = result.get(node.attr, False) or in_collection
        elif isinstance(node, ast.BinOp):
            visit(node.left, in_collection)
            visit(node.right, in_collection)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                visit(elt, in_collection)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # forward reference imbriquée : list["User"]
            try:
                visit(ast.parse(node.value, mode="eval").body, in_collection)
            except SyntaxError:
                pass

    visit(tree.body, False)
    return result


def _extract_types_from_annotation(annotation: str) -> list[str]:
    """Extrait les noms de types candidats (hors builtins/typing) d'une annotation."""
    return [t for t in _classify_annotation_types(annotation) if t not in _IGNORED_TYPE_NAMES]


def _constructed_call_name(default: str | None) -> str | None:
    """Nom (éventuellement pointé) du callable si la valeur par défaut CONSTRUIT une instance.

    'Engine()' -> 'Engine' ; 'mod.Engine(x)' -> 'mod.Engine' ;
    'field(default_factory=Engine)' -> 'Engine' (idem 'dataclasses.field') ;
    '[]' -> 'list' ; '{}' -> 'dict' ; '{1}' -> 'set' ;
    'engine' / 'None' / 'field(default=...)' / lambda -> None.
    """
    if not default:
        return None
    try:
        node = ast.parse(default, mode="eval").body
    except SyntaxError:
        return None
    if isinstance(node, (ast.List, ast.ListComp)):
        return "list"
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return "dict"
    if isinstance(node, (ast.Set, ast.SetComp)):
        return "set"
    if not isinstance(node, ast.Call):
        return None
    func = ast.unparse(node.func)
    if func in ("field", "dataclasses.field"):
        for kw in node.keywords:
            # default_factory=lambda: ... n'est pas une construction identifiable
            if kw.arg == "default_factory" and isinstance(kw.value, (ast.Name, ast.Attribute)):
                return ast.unparse(kw.value)
        return None  # field(default=...) : valeur partagée, pas une construction
    return func


def _classify_attribute_relation(
    attr_default: str | None, type_name: str, in_collection: bool
) -> RelationType:
    """Classifie la relation portée par un attribut typé.

    Sémantique : composition = instance ou conteneur construit par la classe ;
    agrégation = collection typée reçue ; association = référence stockée.
    """
    ctor = _constructed_call_name(attr_default)
    ctor_short = ctor.split(".")[-1] if ctor else None
    if in_collection:
        if ctor_short in _COLLECTION_TYPES:
            # la classe construit son conteneur (field(default_factory=list),
            # self.items: list[X] = []) : elle en possède le cycle de vie
            return RelationType.COMPOSITION
        return RelationType.AGGREGATION
    if ctor_short == type_name:  # noms courts : gère aussi mod.Engine()
        return RelationType.COMPOSITION
    return RelationType.ASSOCIATION


def _resolve_simple(
    simple: str,
    name_map: dict[str, list[str]],
    current_module: str | None,
) -> str | None:
    """Résout un nom simple vers un nom qualifié : module courant d'abord, puis ordre trié."""
    candidates = sorted(name_map.get(simple, ()))
    if not candidates:
        return None
    if current_module:
        exact_local = f"{current_module}.{simple}"
        if exact_local in candidates:
            return exact_local
        prefixed = [c for c in candidates if c.startswith(current_module + ".")]
        if prefixed:
            return prefixed[0]
    return candidates[0]


def _resolve_class_name(
    name: str,
    name_map: dict[str, list[str]],
    qualified_set: set[str],
    current_module: str | None = None,
) -> str | None:
    """Résout un nom de classe (simple, qualifié ou générique) vers un nom qualifié."""
    clean = name.split("[")[0]
    if clean in qualified_set:
        return clean
    if "." in clean:
        suffix_matches = sorted(q for q in qualified_set if q.endswith(f".{clean}"))
        if suffix_matches:
            return suffix_matches[0]
    return _resolve_simple(clean.split(".")[-1], name_map, current_module)


def detect_relationships(classes: list[ClassInfo]) -> list[RelationInfo]:
    """Détecte les relations : héritage, composition, agrégation, association, dépendance."""
    relations: list[RelationInfo] = []

    name_to_qualified: dict[str, list[str]] = defaultdict(list)
    for cls in classes:
        name_to_qualified[cls.name.split(".")[-1]].append(cls.qualified_name)
    qualified_set = {c.qualified_name for c in classes}

    # ordre stable quel que soit l'ordre d'entrée
    for cls in sorted(classes, key=lambda c: c.qualified_name):
        # Héritage
        for base in cls.bases:
            target = _resolve_class_name(base, name_to_qualified, qualified_set, cls.module)
            if target and target != cls.qualified_name:
                relations.append(
                    RelationInfo(
                        source=cls.qualified_name,
                        target=target,
                        relation_type=RelationType.INHERITANCE,
                    )
                )

        # Composition / agrégation / association via attributs typés
        for attr in cls.attributes:
            if not attr.type_annotation:
                continue
            type_flags = _classify_annotation_types(attr.type_annotation)
            for type_name, in_collection in type_flags.items():
                if type_name in _IGNORED_TYPE_NAMES:
                    continue
                target = _resolve_simple(type_name, name_to_qualified, cls.module)
                if not target or target == cls.qualified_name:
                    continue
                rel_type = _classify_attribute_relation(attr.default, type_name, in_collection)
                relations.append(
                    RelationInfo(
                        source=cls.qualified_name,
                        target=target,
                        relation_type=rel_type,
                        label=attr.name,
                    )
                )

        # Dépendances via paramètres et retours de méthodes
        attr_related = {
            (r.source, r.target)
            for r in relations
            if r.relation_type
            in (RelationType.COMPOSITION, RelationType.AGGREGATION, RelationType.ASSOCIATION)
        }

        def add_dependency(
            annotation: str,
            label: str,
            current: ClassInfo,
            existing: set[tuple[str, str]],
        ) -> None:
            for type_name in _extract_types_from_annotation(annotation):
                if type_name == current.name.split(".")[-1]:
                    continue
                target = _resolve_simple(type_name, name_to_qualified, current.module)
                if not target or target == current.qualified_name:
                    continue
                if (current.qualified_name, target) in existing:
                    continue
                relations.append(
                    RelationInfo(
                        source=current.qualified_name,
                        target=target,
                        relation_type=RelationType.DEPENDENCY,
                        label=label,
                    )
                )

        for method in cls.methods:
            for _, param_type in method.parameters:
                if param_type:
                    add_dependency(param_type, f"{method.name} param", cls, attr_related)
            if method.return_type:
                add_dependency(method.return_type, f"{method.name} return", cls, attr_related)

    # Dédupliquer (source, target, type)
    seen: set[tuple[str, str, RelationType]] = set()
    deduped: list[RelationInfo] = []
    for r in relations:
        key = (r.source, r.target, r.relation_type)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def detect_circular_dependencies(dependencies: dict[str, set[str]]) -> list[list[str]]:
    """Détecte les cycles de dépendances (DFS itératif, cycles normalisés sans doublon).

    Chaque cycle est retourné sous forme canonique : rotation lexicographiquement
    minimale, sans répéter le premier nœud à la fin.
    """
    cycles: list[list[str]] = []
    seen_cycles: set[tuple[str, ...]] = set()
    visited: set[str] = set()

    for start in sorted(dependencies):
        if start in visited:
            continue
        visited.add(start)
        path = [start]
        on_stack = {start}
        stack: list[tuple[str, list[str]]] = [(start, sorted(dependencies.get(start, ())))]

        while stack:
            node, neighbors = stack[-1]
            advanced = False
            while neighbors:
                neighbor = neighbors.pop(0)
                if neighbor not in visited:
                    visited.add(neighbor)
                    on_stack.add(neighbor)
                    path.append(neighbor)
                    stack.append((neighbor, sorted(dependencies.get(neighbor, ()))))
                    advanced = True
                    break
                if neighbor in on_stack:
                    cycle = path[path.index(neighbor):]
                    key = _normalize_cycle(cycle)
                    if key and key not in seen_cycles:
                        seen_cycles.add(key)
                        cycles.append(list(key))
            if not advanced:
                stack.pop()
                on_stack.discard(node)
                path.pop()

    return cycles


def _normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Normalise un cycle pour comparaison : sans endpoint dupliqué, rotation minimale."""
    if not cycle:
        return ()
    if len(cycle) > 1 and cycle[0] == cycle[-1]:
        cycle = cycle[:-1]
    if not cycle:
        return ()
    n = len(cycle)
    rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(n)]
    return min(rotations)


def cycle_display(cycle: list[str]) -> str:
    """Formate un cycle pour affichage en refermant la boucle : a -> b -> a."""
    if not cycle:
        return ""
    if len(cycle) == 1:
        return f"{cycle[0]} -> {cycle[0]}"
    return " -> ".join([*cycle, cycle[0]])


def get_focused_subgraph(
    package_classes: dict[str, ClassInfo],
    relations: list[RelationInfo],
    focus_class: str,
    depth: int = 2,
) -> tuple[dict[str, ClassInfo], list[RelationInfo]]:
    """Retourne le sous-graphe (non dirigé) centré sur une classe, à N niveaux."""
    focus_qualified = None
    if focus_class in package_classes:
        focus_qualified = focus_class
    else:
        candidates = sorted(
            q
            for q in package_classes
            if q.endswith(f".{focus_class}") or q.split(".")[-1] == focus_class
        )
        if candidates:
            focus_qualified = candidates[0]
        else:
            available = ", ".join(sorted(package_classes)[:10])
            raise ValueError(
                f"Classe focus '{focus_class}' non trouvée. Classes disponibles: {available}"
            )

    adj: dict[str, set[str]] = defaultdict(set)
    for rel in relations:
        adj[rel.source].add(rel.target)
        adj[rel.target].add(rel.source)

    visited = {focus_qualified}
    collected = {focus_qualified}
    queue = deque([(focus_qualified, 0)])

    while queue:
        current, d = queue.popleft()
        if d >= depth:
            continue
        for neighbor in sorted(adj.get(current, ())):
            if neighbor not in visited:
                visited.add(neighbor)
                collected.add(neighbor)
                queue.append((neighbor, d + 1))

    focused_classes = {q: package_classes[q] for q in collected if q in package_classes}
    focused_relations = [r for r in relations if r.source in collected and r.target in collected]

    return focused_classes, focused_relations
