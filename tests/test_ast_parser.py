"""Tests du parseur AST (extraction classes, membres, fonctions)."""

from pathlib import Path

from gendoc.analyzer.ast_parser import parse_file_for_classes


def _parse(tmp_path: Path, source: str):
    f = tmp_path / "mod.py"
    f.write_text(source)
    return parse_file_for_classes(f, "pkg.mod")


def test_nested_class_not_merged_into_parent(tmp_path: Path):
    """Les classes imbriquées sont émises séparément, sans fuir dans la classe englobante."""
    classes = _parse(
        tmp_path,
        """
class Outer:
    outer_var: int = 0

    class Inner:
        inner_var: str = "x"

        def secret(self):
            pass

    def outer_method(self):
        pass
""",
    )
    by_name = {c.name: c for c in classes}

    assert "Outer" in by_name
    assert "Outer.Inner" in by_name

    outer = by_name["Outer"]
    assert "secret" not in {m.name for m in outer.methods}
    assert "inner_var" not in {a.name for a in outer.attributes}
    assert "outer_method" in {m.name for m in outer.methods}

    inner = by_name["Outer.Inner"]
    assert "secret" in {m.name for m in inner.methods}
    assert "inner_var" in {a.name for a in inner.attributes}


def test_instance_attributes_not_marked_class_attributes(tmp_path: Path):
    """self.x: T dans __init__ et les champs de dataclass ne sont pas des attributs de classe."""
    classes = _parse(
        tmp_path,
        """
class C:
    class_var: int = 0

    def __init__(self):
        self.inst: str = "x"
        self.plain = 1
""",
    )
    attrs = {a.name: a for a in classes[0].attributes}

    assert attrs["class_var"].is_class_attribute is True
    assert attrs["inst"].is_class_attribute is False
    assert attrs["plain"].is_class_attribute is False


def test_closure_in_init_is_not_a_method(tmp_path: Path):
    """Une fonction définie dans __init__ n'est pas une méthode de la classe."""
    classes = _parse(
        tmp_path,
        """
class C:
    def __init__(self):
        def helper():
            pass

        self.x = helper
""",
    )
    assert "helper" not in {m.name for m in classes[0].methods}
    assert "x" in {a.name for a in classes[0].attributes}


def test_init_attributes_in_conditionals_are_found(tmp_path: Path):
    """Les self.x assignés sous if/try dans __init__ sont détectés."""
    classes = _parse(
        tmp_path,
        """
class C:
    def __init__(self, flag):
        if flag:
            self.a = 1
        else:
            self.b = 2
        try:
            self.c = 3
        except Exception:
            pass
""",
    )
    attr_names = {a.name for a in classes[0].attributes}
    assert {"a", "b", "c"} <= attr_names


def test_positional_only_params_captured(tmp_path: Path):
    """Les paramètres positional-only (avant /) apparaissent dans la signature."""
    classes = _parse(
        tmp_path,
        """
class C:
    def m(self, a, /, b, *, c):
        pass
""",
    )
    params = [n for n, _ in classes[0].methods[0].parameters]
    assert params == ["self", "a", "b", "c"]


def test_async_method_flagged(tmp_path: Path):
    """async def est marqué is_async."""
    classes = _parse(
        tmp_path,
        """
class C:
    async def fetch(self):
        pass

    def sync(self):
        pass
""",
    )
    methods = {m.name: m for m in classes[0].methods}
    assert methods["fetch"].is_async is True
    assert methods["sync"].is_async is False


def test_string_annotation_unquoted(tmp_path: Path):
    """x: "User" ne doit pas garder ses quotes dans le type affiché."""
    classes = _parse(
        tmp_path,
        """
class User:
    pass


class C:
    ref: "User" = None
""",
    )
    by_name = {c.name: c for c in classes}
    attr = by_name["C"].attributes[0]
    assert attr.type_annotation == "User"


def test_enum_class_has_stereotype_and_value_members(tmp_path):
    """Une Enum est stéréotypée 'enum' et ses membres n'ont pas de type inféré."""
    f = tmp_path / "colors.py"
    f.write_text(
        "from enum import Enum\n\n"
        "class Color(Enum):\n"
        "    RED = 1\n"
        "    GREEN = 2\n"
    )

    classes = parse_file_for_classes(f, "colors")

    color = next(c for c in classes if c.name == "Color")
    assert color.stereotype == "enum"
    members = {a.name: a for a in color.attributes}
    assert members["RED"].type_annotation is None
    assert members["RED"].default == "1"


def test_dataclass_has_stereotype(tmp_path):
    """@dataclass (nu ou paramétré, importé ou qualifié) est stéréotypé 'dataclass'."""
    f = tmp_path / "dc.py"
    f.write_text(
        "import dataclasses\n"
        "from dataclasses import dataclass\n\n"
        "@dataclass\n"
        "class Plain:\n"
        "    x: int = 0\n\n"
        "@dataclasses.dataclass(frozen=True)\n"
        "class Frozen:\n"
        "    y: int = 0\n\n"
        "class Normal:\n"
        "    pass\n"
    )

    classes = {c.name: c for c in parse_file_for_classes(f, "dc")}

    assert classes["Plain"].stereotype == "dataclass"
    assert classes["Frozen"].stereotype == "dataclass"
    assert classes["Normal"].stereotype is None
