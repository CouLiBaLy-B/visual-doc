"""Tests renderers."""

from pathlib import Path

import pytest

from gendoc.analyzer import analyze_package
from gendoc.analyzer.models import AttributeInfo, ClassInfo, MethodInfo, ModuleInfo, PackageInfo
from gendoc.analyzer.relationships import detect_relationships
from gendoc.renderers import (
    generate_class_diagram_mermaid,
    generate_class_diagram_plantuml,
    generate_class_diagram_svg,
    generate_module_class_diagram_mermaid,
    generate_package_diagram_mermaid,
    generate_package_diagram_plantuml,
    generate_package_diagram_svg,
)


@pytest.fixture
def sample_package(temp_package):
    return analyze_package(temp_package, package_name="testpkg")


@pytest.fixture
def chord_package(tmp_path: Path) -> PackageInfo:
    """Cycle a->b->c->a plus une corde a->c (hors cycle)."""
    pkg = PackageInfo(name="p", root_path=tmp_path)
    pkg.modules = {
        m: ModuleInfo(name=m, file_path=tmp_path / f"{m}.py", dotted_path=m)
        for m in ("a", "b", "c")
    }
    pkg.dependencies = {"a": {"b", "c"}, "b": {"c"}, "c": {"a"}}
    pkg.circular_dependencies = [["a", "b", "c"]]
    return pkg


def test_mermaid_class_diagram(sample_package):
    mermaid = generate_class_diagram_mermaid(sample_package.classes, sample_package.relations)

    assert "classDiagram" in mermaid
    assert "class" in mermaid
    # Vérifier qu'une classe connue apparaît
    assert "User" in mermaid
    # Relations héritage
    assert "<|--" in mermaid


def test_plantuml_class_diagram(sample_package):
    puml = generate_class_diagram_plantuml(sample_package.classes, sample_package.relations)

    assert "@startuml" in puml
    assert "@enduml" in puml
    assert "class" in puml
    assert "User" in puml


def test_mermaid_package_diagram(sample_package):
    mermaid = generate_package_diagram_mermaid(sample_package)

    assert "flowchart TD" in mermaid
    assert "-->" in mermaid or "flowchart" in mermaid


def test_plantuml_package_diagram(sample_package):
    puml = generate_package_diagram_plantuml(sample_package)

    assert "@startuml" in puml
    assert "package" in puml or "[" in puml


def test_svg_class_diagram(sample_package):
    svg = generate_class_diagram_svg(sample_package.classes, sample_package.relations)

    assert "<svg" in svg
    assert "User" in svg


def test_svg_package_diagram(sample_package):
    svg = generate_package_diagram_svg(sample_package)

    assert "<svg" in svg
    # module name devrait apparaître
    assert "testpkg" in svg or "models" in svg


def test_svg_empty():
    svg = generate_class_diagram_svg({}, [])

    assert "<svg" in svg


def test_module_mermaid_diagram(sample_package):
    # Prendre un module
    mod = sample_package.modules["testpkg.models"]
    mermaid = generate_module_class_diagram_mermaid(
        "testpkg.models", mod.classes, sample_package.relations
    )

    assert "classDiagram" in mermaid
    assert "User" in mermaid


def test_mermaid_public_only(sample_package):
    mermaid = generate_class_diagram_mermaid(
        sample_package.classes, sample_package.relations, public_only=True
    )

    assert "classDiagram" in mermaid


def test_circular_highlight_svg(sample_package):
    # le fixture contient bien un cycle (circular_a <-> circular_b)
    assert sample_package.circular_dependencies
    svg = generate_package_diagram_svg(sample_package)
    assert "dep-circular" in svg


def _cls(name: str, module: str, **kwargs) -> ClassInfo:
    return ClassInfo(name=name, module=module, file_path=Path(f"{module}.py"), **kwargs)


def test_mermaid_homonym_classes_not_merged():
    """Deux classes User de modules différents restent deux nœuds distincts."""
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.b", bases=["User"])
    classes = {c.qualified_name: c for c in (a_user, b_user, admin)}
    rels = detect_relationships(list(classes.values()))

    mermaid = generate_class_diagram_mermaid(classes, rels)

    assert "pkg_a_User" in mermaid
    assert "pkg_b_User" in mermaid
    assert "pkg_b_User <|-- pkg_b_Admin" in mermaid


def test_plantuml_homonym_classes_not_merged():
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    admin = _cls("Admin", "pkg.b", bases=["User"])
    classes = {c.qualified_name: c for c in (a_user, b_user, admin)}
    rels = detect_relationships(list(classes.values()))

    puml = generate_class_diagram_plantuml(classes, rels)

    assert 'class "User" as pkg_a_User' in puml
    assert 'class "User" as pkg_b_User' in puml
    assert "pkg_b_User <|-- pkg_b_Admin" in puml


def test_svg_homonym_classes_have_distinct_positions():
    a_user = _cls("User", "pkg.a")
    b_user = _cls("User", "pkg.b")
    classes = {c.qualified_name: c for c in (a_user, b_user)}

    svg = generate_class_diagram_svg(classes, [])

    import re

    xs = re.findall(r'<rect x="(\d+)" y="(\d+)"', svg)
    assert len(set(xs)) == 2  # deux boîtes à des positions distinctes


def test_mermaid_empty_diagram_is_valid():
    """Un module sans classe doit produire du Mermaid valide, pas un classDiagram vide."""
    out = generate_class_diagram_mermaid({}, [], title="Module agent_recruiter.main")

    # une instruction réelle en plus de l'en-tête et du commentaire de titre
    body = [
        line.strip()
        for line in out.splitlines()
        if line.strip() and not line.strip().startswith("%%") and line.strip() != "classDiagram"
    ]
    assert body, "un classDiagram vide (en-tête + commentaire seul) est rejeté par Mermaid"
    assert any("note" in line for line in body)


def test_module_mermaid_no_classes_is_valid(tmp_path):
    """Le diagramme d'un module réel sans classe (que des fonctions) reste valide."""
    from gendoc.analyzer import analyze_package

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "main.py").write_text("def run():\n    return 1\n")

    pkg = analyze_package(pkg_dir, package_name="pkg")
    mod = pkg.modules["pkg.main"]
    out = generate_module_class_diagram_mermaid("pkg.main", mod.classes, pkg.relations)

    body = [
        line.strip()
        for line in out.splitlines()
        if line.strip() and not line.strip().startswith("%%") and line.strip() != "classDiagram"
    ]
    assert body


def test_mermaid_no_bare_separator_line(sample_package):
    """Pas de ligne '--' (syntaxe PlantUML) dans les corps de classes Mermaid."""
    mermaid = generate_class_diagram_mermaid(sample_package.classes, sample_package.relations)

    assert not any(line.strip() == "--" for line in mermaid.splitlines())


def test_mermaid_generics_use_tilde(sample_package):
    """Les génériques utilisent la syntaxe Mermaid ~T~ au lieu des crochets."""
    mermaid = generate_class_diagram_mermaid(sample_package.classes, sample_package.relations)

    assert "List~Product~" in mermaid  # Order.products: List[Product]
    assert "List[Product]" not in mermaid


def test_plantuml_docstring_cannot_break_note():
    """Un docstring contenant 'end note' ne casse pas le bloc note PlantUML."""
    c = _cls("C", "m", docstring="end note\nboom")

    puml = generate_class_diagram_plantuml({c.qualified_name: c}, [])

    assert puml.count("end note") == 1  # uniquement le terminateur


def test_package_mermaid_chord_edge_not_marked_circular(chord_package):
    mmd = generate_package_diagram_mermaid(chord_package)

    assert "a -->|circular| b" in mmd
    assert "c -->|circular| a" in mmd  # arête de fermeture du cycle
    assert "a -->|circular| c" not in mmd  # la corde n'est pas dans le cycle
    assert "    a --> c" in mmd


def test_package_mermaid_linkstyle_matches_circular_edges(chord_package):
    mmd = generate_package_diagram_mermaid(chord_package)

    linkstyles = [line for line in mmd.splitlines() if "linkStyle" in line]
    assert len(linkstyles) == 3  # a->b, b->c, c->a


def test_package_plantuml_chord_edge_not_red(chord_package):
    puml = generate_package_diagram_plantuml(chord_package)

    assert puml.count("#red") == 3


def test_package_svg_chord_edge_not_red(chord_package):
    svg = generate_package_diagram_svg(chord_package)

    assert svg.count('class="dep-circular"') == 3


def test_svg_truncated_member_has_ellipsis():
    c = _cls(
        "C",
        "m",
        # nom volontairement très long pour dépasser la largeur de boîte
        methods=[MethodInfo(name="une_methode_avec_un_nom_vraiment_tres_long_pour_depasser")],
    )

    svg = generate_class_diagram_svg({c.qualified_name: c}, [])

    assert "…" in svg


def test_svg_rows_do_not_overlap():
    """Les boîtes hautes ne débordent pas sur la rangée suivante."""
    import re

    def busy(name):
        return _cls(
            name,
            "m",
            attributes=[AttributeInfo(name=f"attr_{i}") for i in range(5)],
            methods=[MethodInfo(name=f"meth_{i}") for i in range(6)],
        )

    classes = {c.qualified_name: c for c in (busy("A"), busy("B"), busy("C"), busy("D"))}

    svg = generate_class_diagram_svg(classes, [])

    rects = [
        (int(x), int(y), int(h))
        for x, y, h in re.findall(r'<rect x="(\d+)" y="(\d+)" width="\d+" height="(\d+)"', svg)
    ]
    assert len(rects) == 4
    by_col: dict[int, list[tuple[int, int]]] = {}
    for x, y, h in rects:
        by_col.setdefault(x, []).append((y, h))
    for col in by_col.values():
        col.sort()
        for (y1, h1), (y2, _h2) in zip(col, col[1:], strict=False):
            assert y2 >= y1 + h1, "chevauchement vertical de boîtes"


def test_escape_mermaid_type_union_and_generics():
    """L'échappement Mermaid neutralise | (unions) et , (génériques)."""
    from gendoc.renderers.common import escape_mermaid_type

    assert escape_mermaid_type("dict[str, Item | None]") == "dict~str‚ Item ¦ None~"


def test_mermaid_union_types_have_no_raw_pipe():
    """Un membre typé `X | None` ne contient pas de | brut (aléa de parsing Mermaid)."""
    c = _cls(
        "Holder",
        "m",
        attributes=[
            AttributeInfo(name="note", type_annotation="str | None"),
            AttributeInfo(name="store", type_annotation="dict[str, object]"),
        ],
        methods=[MethodInfo(name="find", parameters=[("self", None), ("q", "str | None")])],
    )

    mermaid = generate_class_diagram_mermaid({c.qualified_name: c}, [])

    # n'inspecter que les lignes de membres (les arêtes <|-- portent un | légitime)
    member_lines = [line for line in mermaid.splitlines() if line.startswith("        ")]
    assert member_lines
    assert not any("|" in line for line in member_lines)
    assert "+note str ¦ None" in mermaid
    assert "+store dict~str‚ object~" in mermaid


def test_mermaid_method_param_separator_comma_preserved():
    """La virgule entre paramètres reste brute ; seule celle des génériques est échappée."""
    c = _cls(
        "Svc",
        "m",
        methods=[MethodInfo(name="run", parameters=[("self", None), ("a", "int"), ("b", "str")])],
    )

    mermaid = generate_class_diagram_mermaid({c.qualified_name: c}, [])

    assert "+run(a: int, b: str)" in mermaid


def test_stereotypes_rendered_in_mermaid_and_plantuml():
    """Les classes enum/dataclass portent leur stéréotype dans les deux formats."""
    color = _cls("Color", "m", stereotype="enum")
    order = _cls("Order", "m", stereotype="dataclass")
    plain = _cls("Plain", "m")
    classes = {c.qualified_name: c for c in (color, order, plain)}

    mermaid = generate_class_diagram_mermaid(classes, [])
    puml = generate_class_diagram_plantuml(classes, [])

    assert "<<enumeration>>" in mermaid and "<<dataclass>>" in mermaid
    assert 'as m_Color <<enumeration>>' in puml
    assert 'as m_Order <<dataclass>>' in puml
    assert 'as m_Plain {' in puml
    assert mermaid.count("<<") == 2  # rien sur la classe sans stéréotype
