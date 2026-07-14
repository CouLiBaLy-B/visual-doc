"""Détection des relations entre classes."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ClassInfo, RelationInfo

from .models import RelationType, RelationInfo


def detect_relationships(classes: list["ClassInfo"]) -> list["RelationInfo"]:
    """Détecte les relations entre classes: héritage, composition, etc."""
    relations: list[RelationInfo] = []
    # Map simple name -> qualified names
    name_to_qualified: dict[str, list[str]] = defaultdict(list)
    for cls in classes:
        name_to_qualified[cls.name].append(cls.qualified_name)
        # aussi dotted path sans module? On mappe

    qualified_set = {c.qualified_name for c in classes}
    simple_names = {c.name for c in classes}

    for cls in classes:
        # Héritage
        for base in cls.bases:
            # base peut être simple ou qualified
            base_simple = base.split(".")[-1].split("[")[0]  # enlever generics
            target = _resolve_class_name(base, name_to_qualified, qualified_set)
            if target:
                relations.append(
                    RelationInfo(
                        source=cls.qualified_name,
                        target=target,
                        relation_type=RelationType.INHERITANCE,
                    )
                )
            elif base_simple in simple_names:
                # base dans projet mais pas résolu directement, prendre premier
                candidates = name_to_qualified.get(base_simple, [])
                if candidates:
                    relations.append(
                        RelationInfo(
                            source=cls.qualified_name,
                            target=candidates[0],
                            relation_type=RelationType.INHERITANCE,
                        )
                    )

        # Composition / Association via attributs
        for attr in cls.attributes:
            if not attr.type_annotation:
                continue
            # nettoyer annotation
            ann = attr.type_annotation
            # enlever Optional, List, etc pour extraire classe
            possible_types = _extract_types_from_annotation(ann)
            for p_type in possible_types:
                if p_type in simple_names:
                    # éviter self-reference inutile ? mais garder
                    target_candidates = name_to_qualified.get(p_type, [])
                    for target in target_candidates:
                        if target == cls.qualified_name:
                            continue
                        # déterminer si composition ou association
                        # heuristique: si attribut créé dans __init__ ou avec default new => composition
                        # sinon association
                        rel_type = RelationType.COMPOSITION
                        # Si le type est dans une collection (List[X]), on considère aggregation
                        if any(x in ann for x in ["List", "list", "Sequence", "Set", "Collection"]):
                            rel_type = RelationType.AGGREGATION
                        relations.append(
                            RelationInfo(
                                source=cls.qualified_name,
                                target=target,
                                relation_type=rel_type,
                                label=attr.name,
                            )
                        )

        # Dépendance via méthodes paramètres / return
        for method in cls.methods:
            # paramètres
            for _, param_type in method.parameters:
                if not param_type:
                    continue
                types = _extract_types_from_annotation(param_type)
                for t in types:
                    if t in simple_names and t != cls.name:
                        cand = name_to_qualified.get(t, [])
                        for target in cand:
                            # ne pas dupliquer si déjà composition
                            if not any(
                                r.source == cls.qualified_name
                                and r.target == target
                                and r.relation_type in (RelationType.COMPOSITION, RelationType.AGGREGATION)
                                for r in relations
                            ):
                                relations.append(
                                    RelationInfo(
                                        source=cls.qualified_name,
                                        target=target,
                                        relation_type=RelationType.DEPENDENCY,
                                        label=f"{method.name} param",
                                    )
                                )
            # return type
            if method.return_type:
                types = _extract_types_from_annotation(method.return_type)
                for t in types:
                    if t in simple_names and t != cls.name:
                        cand = name_to_qualified.get(t, [])
                        for target in cand:
                            relations.append(
                                RelationInfo(
                                    source=cls.qualified_name,
                                    target=target,
                                    relation_type=RelationType.DEPENDENCY,
                                    label=f"{method.name} return",
                                )
                            )

    # Dédupliquer
    seen = set()
    deduped: list[RelationInfo] = []
    for r in relations:
        key = (r.source, r.target, r.relation_type)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped


def _resolve_class_name(name: str, name_map: dict[str, list[str]], qualified_set: set[str]) -> str | None:
    """Résout un nom de classe vers qualified name."""
    # nettoyer generics
    clean = name.split("[")[0].split(".")[-1]
    if name in qualified_set:
        return name
    # chercher qualified qui finit par name
    for q in qualified_set:
        if q.endswith(f".{name}") or q.endswith(f".{clean}"):
            return q
    # chercher via map
    if clean in name_map:
        return name_map[clean][0]
    return None


def _extract_types_from_annotation(annotation: str) -> list[str]:
    """Extrait les noms de types d'une annotation."""
    # Très simplifié: split par caractères non identifiants
    # Ex: "Optional[List[MyClass]]" -> ["Optional", "List", "MyClass"]
    # On veut seulement les types qui pourraient être des classes (CamelCase)
    import re

    # Retirer les strings
    # Trouver tous les identifiants
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", annotation)
    # Filtrer les builtins et typing keywords
    ignore = {
        "Optional",
        "List",
        "Dict",
        "Set",
        "Tuple",
        "Union",
        "Any",
        "str",
        "int",
        "float",
        "bool",
        "bytes",
        "None",
        "list",
        "dict",
        "set",
        "tuple",
        "Callable",
        "Iterable",
        "Sequence",
        "Mapping",
        "Type",
        "ClassVar",
        "Final",
        "Literal",
        "Annotated",
        "Self",
    }
    return [t for t in tokens if t not in ignore and len(t) > 1]


def detect_circular_dependencies(dependencies: dict[str, set[str]]) -> list[list[str]]:
    """Détecte les dépendances circulaires via DFS."""

    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: list[str] = []
    on_stack: set[str] = set()

    def dfs(node: str) -> None:
        visited.add(node)
        rec_stack.append(node)
        on_stack.add(node)

        for neighbor in dependencies.get(node, set()):
            if neighbor not in visited:
                dfs(neighbor)
            elif neighbor in on_stack:
                # cycle trouvé
                idx = rec_stack.index(neighbor)
                cycle = rec_stack[idx:] + [neighbor]
                # normaliser cycle pour éviter doublons
                # utiliser tuple trié minimal ?
                if cycle not in cycles and list(reversed(cycle)) not in cycles:
                    # éviter doublons rotationnels
                    normalized = _normalize_cycle(cycle)
                    if normalized not in [tuple(c) for c in cycles]:
                        cycles.append(cycle)

        rec_stack.pop()
        on_stack.remove(node)

    for node in dependencies:
        if node not in visited:
            dfs(node)

    return cycles


def _normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Normalise un cycle pour comparaison (rotation min)."""
    if not cycle:
        return tuple()
    # enlever dernier doublon si même que premier
    if cycle[0] == cycle[-1]:
        cycle = cycle[:-1]
    if not cycle:
        return tuple()
    # trouver rotation lexicographiquement minimale
    n = len(cycle)
    rotations = [tuple(cycle[i:] + cycle[:i]) for i in range(n)]
    return min(rotations)


def get_focused_subgraph(
    package_classes: dict[str, "ClassInfo"],
    relations: list["RelationInfo"],
    focus_class: str,
    depth: int = 2,
) -> tuple[dict[str, "ClassInfo"], list["RelationInfo"]]:
    """Retourne sous-graphe centré sur une classe à N niveaux."""
    # Résoudre focus_class
    focus_qualified = None
    # chercher par nom simple ou qualified
    if focus_class in package_classes:
        focus_qualified = focus_class
    else:
        # chercher par simple name
        candidates = [q for q in package_classes if q.endswith(f".{focus_class}") or q.split(".")[-1] == focus_class]
        if candidates:
            focus_qualified = candidates[0]
        else:
            raise ValueError(f"Classe focus '{focus_class}' non trouvée. Classes disponibles: {list(package_classes.keys())[:10]}")

    # BFS
    visited = {focus_qualified}
    queue = deque([(focus_qualified, 0)])
    # adj list
    adj: dict[str, set[str]] = defaultdict(set)
    for rel in relations:
        adj[rel.source].add(rel.target)
        # pour graphe non dirigé pour focus, ajouter aussi reverse
        adj[rel.target].add(rel.source)

    collected = {focus_qualified}

    while queue:
        current, d = queue.popleft()
        if d >= depth:
            continue
        for neighbor in adj.get(current, []):
            if neighbor not in visited:
                visited.add(neighbor)
                collected.add(neighbor)
                queue.append((neighbor, d + 1))

    # filtrer classes et relations
    focused_classes = {q: package_classes[q] for q in collected if q in package_classes}
    focused_relations = [r for r in relations if r.source in collected and r.target in collected]

    return focused_classes, focused_relations
