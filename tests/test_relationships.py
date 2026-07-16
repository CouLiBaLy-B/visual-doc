"""Tests de la détection de relations et de cycles."""

from pathlib import Path

from gendoc.analyzer.models import AttributeInfo, ClassInfo, RelationType
from gendoc.analyzer.relationships import (
    detect_circular_dependencies,
    detect_relationships,
)


def _cls(name: str, module: str, **kwargs) -> ClassInfo:
    return ClassInfo(name=name, module=module, file_path=Path(f"{module}.py"), **kwargs)


def test_inheritance_prefers_same_module_on_name_collision():
    """Deux modules définissent User : Admin(User) de pkg.b doit hériter de pkg.b.User."""
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.b", bases=["User"])

    rels = detect_relationships([a_user, b_user, admin])

    inh = [r for r in rels if r.relation_type == RelationType.INHERITANCE]
    assert len(inh) == 1
    assert inh[0].source == "pkg.b.Admin"
    assert inh[0].target == "pkg.b.User"


def test_attribute_reference_resolves_to_single_local_target():
    """Un attribut typé vers un nom homonyme ne crée qu'une relation, vers le module local."""
    a_item = _cls("Item", "pkg.a")
    b_item = _cls("Item", "pkg.b")
    holder = _cls(
        "Holder",
        "pkg.b",
        attributes=[AttributeInfo(name="item", type_annotation="Item")],
    )

    rels = detect_relationships([a_item, b_item, holder])

    targeted = [r for r in rels if r.source == "pkg.b.Holder"]
    assert len(targeted) == 1
    assert targeted[0].target == "pkg.b.Item"


def test_class_named_like_collection_is_not_aggregation():
    """'Blocklist' contient 'list' mais n'est pas une collection : pas d'AGGREGATION."""
    blocklist = _cls("Blocklist", "m")
    c = _cls(
        "C",
        "m",
        attributes=[AttributeInfo(name="b", type_annotation="Blocklist", default="Blocklist()")],
    )

    rels = detect_relationships([blocklist, c])

    rel = next(r for r in rels if r.target == "m.Blocklist")
    assert rel.relation_type != RelationType.AGGREGATION


def test_collection_of_project_class_is_aggregation():
    """list[Item] / List[Item] / Optional[List[Item]] → AGGREGATION."""
    item = _cls("Item", "m")
    for ann in ("list[Item]", "List[Item]", "Optional[List[Item]]", "dict[str, Item]"):
        c = _cls("C", "m", attributes=[AttributeInfo(name="items", type_annotation=ann)])
        rels = detect_relationships([item, c])
        rel = next(r for r in rels if r.target == "m.Item")
        assert rel.relation_type == RelationType.AGGREGATION, ann


def test_constructed_in_init_is_composition_else_association():
    """self.x = Engine() → COMPOSITION ; self.x = engine (paramètre) → ASSOCIATION."""
    engine = _cls("Engine", "m")
    owner = _cls(
        "Owner",
        "m",
        attributes=[AttributeInfo(name="engine", type_annotation="Engine", default="Engine()")],
    )
    borrower = _cls(
        "Borrower",
        "m",
        attributes=[AttributeInfo(name="engine", type_annotation="Engine", default="engine")],
    )

    rels = detect_relationships([engine, owner, borrower])

    owner_rel = next(r for r in rels if r.source == "m.Owner")
    borrower_rel = next(r for r in rels if r.source == "m.Borrower")
    assert owner_rel.relation_type == RelationType.COMPOSITION
    assert borrower_rel.relation_type == RelationType.ASSOCIATION


def test_union_annotation_detected():
    """x: Item | None crée une relation vers Item."""
    item = _cls("Item", "m")
    c = _cls("C", "m", attributes=[AttributeInfo(name="x", type_annotation="Item | None")])

    rels = detect_relationships([item, c])

    assert any(r.target == "m.Item" for r in rels)


def test_cycles_normalized_without_duplicate_endpoint():
    deps = {"a": {"b"}, "b": {"a"}}

    cycles = detect_circular_dependencies(deps)

    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["a", "b"]
    assert cycles[0][0] != cycles[0][-1]


def test_same_cycle_reported_once():
    """Un cycle à 3 nœuds atteignable par plusieurs chemins n'est rapporté qu'une fois."""
    deps = {
        "entry1": {"b"},
        "entry2": {"c"},
        "b": {"c"},
        "c": {"d"},
        "d": {"b"},
    }

    cycles = detect_circular_dependencies(deps)

    assert len(cycles) == 1
    assert sorted(cycles[0]) == ["b", "c", "d"]


def test_deep_dependency_chain_no_recursion_error():
    """Un graphe profond (> limite de récursion) ne doit pas crasher."""
    n = 5000
    deps = {f"m{i}": {f"m{i + 1}"} for i in range(n)}
    deps[f"m{n}"] = set()

    assert detect_circular_dependencies(deps) == []


def test_relations_are_deterministic_across_input_order():
    """Le même ensemble de classes donne les mêmes relations quel que soit l'ordre d'entrée."""
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.c", bases=["User"])
    classes = [a_user, b_user, admin]

    def keyset(rels):
        return {(r.source, r.target, r.relation_type) for r in rels}

    ref = keyset(detect_relationships(classes))
    assert keyset(detect_relationships(list(reversed(classes)))) == ref
    # sans module local, la cible homonyme est choisie par ordre lexicographique
    assert ("pkg.c.Admin", "pkg.a.User", RelationType.INHERITANCE) in ref


def test_dataclass_default_factory_object_is_composition():
    """field(default_factory=Engine) : l'instance est construite par la classe."""
    engine = _cls("Engine", "m")
    owner = _cls(
        "Owner",
        "m",
        attributes=[
            AttributeInfo(
                name="engine",
                type_annotation="Engine",
                default="field(default_factory=Engine)",
            )
        ],
    )

    rels = detect_relationships([engine, owner])

    rel = next(r for r in rels if r.source == "m.Owner")
    assert rel.relation_type == RelationType.COMPOSITION


def test_dataclass_default_factory_list_is_composition():
    """field(default_factory=list) sur List[Item] : le conteneur appartient à la classe."""
    item = _cls("Item", "m")
    order = _cls(
        "Order",
        "m",
        attributes=[
            AttributeInfo(
                name="items",
                type_annotation="List[Item]",
                default="field(default_factory=list)",
            )
        ],
    )

    rels = detect_relationships([item, order])

    rel = next(r for r in rels if r.target == "m.Item")
    assert rel.relation_type == RelationType.COMPOSITION


def test_collection_without_construction_stays_aggregation():
    """Collection typée reçue (non construite par la classe) : AGGREGATION."""
    item = _cls("Item", "m")
    for default in (None, "items"):
        c = _cls(
            "C",
            "m",
            attributes=[
                AttributeInfo(name="items", type_annotation="list[Item]", default=default)
            ],
        )
        rels = detect_relationships([item, c])
        rel = next(r for r in rels if r.target == "m.Item")
        assert rel.relation_type == RelationType.AGGREGATION, default


def test_qualified_constructor_is_composition():
    """self.engine = core.Engine() : construction qualifiée reconnue."""
    engine = _cls("Engine", "m.core")
    owner = _cls(
        "Owner",
        "m.app",
        attributes=[
            AttributeInfo(name="engine", type_annotation="Engine", default="core.Engine()")
        ],
    )

    rels = detect_relationships([engine, owner])

    rel = next(r for r in rels if r.source == "m.app.Owner")
    assert rel.relation_type == RelationType.COMPOSITION


def test_optional_union_constructed_is_composition():
    """Engine | None construit → COMPOSITION ; initialisé à None → ASSOCIATION."""
    engine = _cls("Engine", "m")
    built = _cls(
        "Built",
        "m",
        attributes=[
            AttributeInfo(name="engine", type_annotation="Engine | None", default="Engine()")
        ],
    )
    lazy = _cls(
        "Lazy",
        "m",
        attributes=[
            AttributeInfo(name="engine", type_annotation="Engine | None", default="None")
        ],
    )

    rels = detect_relationships([engine, built, lazy])

    assert (
        next(r for r in rels if r.source == "m.Built").relation_type == RelationType.COMPOSITION
    )
    assert (
        next(r for r in rels if r.source == "m.Lazy").relation_type == RelationType.ASSOCIATION
    )


def test_init_list_literal_is_composition():
    """self.users: List[User] = [] : le conteneur est construit par la classe."""
    user = _cls("User", "m")
    svc = _cls(
        "Svc",
        "m",
        attributes=[AttributeInfo(name="users", type_annotation="List[User]", default="[]")],
    )

    rels = detect_relationships([user, svc])

    rel = next(r for r in rels if r.target == "m.User")
    assert rel.relation_type == RelationType.COMPOSITION


def test_field_default_without_factory_is_association():
    """field(default=None) ne construit rien : simple référence."""
    engine = _cls("Engine", "m")
    holder = _cls(
        "Holder",
        "m",
        attributes=[
            AttributeInfo(
                name="engine",
                type_annotation="Engine | None",
                default="field(default=None)",
            )
        ],
    )

    rels = detect_relationships([engine, holder])

    rel = next(r for r in rels if r.source == "m.Holder")
    assert rel.relation_type == RelationType.ASSOCIATION


def test_homonym_fallback_is_reported():
    """La résolution alphabétique d'un homonyme hors module courant est signalée."""
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.c", bases=["User"])

    warnings: list[str] = []
    rels = detect_relationships([a_user, b_user, admin], warnings=warnings)

    # résolution inchangée (déterministe, 1er candidat alphabétique)
    assert any(
        r.source == "pkg.c.Admin"
        and r.target == "pkg.a.User"
        and r.relation_type == RelationType.INHERITANCE
        for r in rels
    )
    assert len(warnings) == 1
    assert "User" in warnings[0]
    assert "pkg.a.User" in warnings[0] and "pkg.b.User" in warnings[0]
    assert "pkg.c.Admin" in warnings[0]


def test_no_warning_when_local_module_resolves_homonym():
    """Pas de signalement quand le module courant lève l'ambiguïté."""
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.b", bases=["User"])

    warnings: list[str] = []
    detect_relationships([a_user, b_user, admin], warnings=warnings)

    assert warnings == []
