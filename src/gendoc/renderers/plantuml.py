"""Générateur PlantUML."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..analyzer.models import ClassInfo, RelationInfo

from ..analyzer.models import RelationType


def generate_class_diagram_plantuml(
    classes: dict[str, "ClassInfo"],
    relations: list["RelationInfo"],
    public_only: bool = False,
    title: str | None = None,
) -> str:
    """Génère diagramme PlantUML."""
    lines = ["@startuml"]
    if title:
        lines.append(f"title {title}")
    lines.append("skinparam classAttributeIconSize 0")
    lines.append("skinparam classFontStyle bold")
    lines.append("hide empty members")

    sorted_classes = sorted(classes.values(), key=lambda c: c.name)

    for cls in sorted_classes:
        lines.append(f"class {cls.name} {{")
        # Attributs
        attrs = cls.attributes
        if public_only:
            attrs = [a for a in attrs if a.visibility.value == "public"]
        for attr in attrs:
            lines.append(f"    {attr.plantuml_str()}")
        if attrs and cls.methods:
            lines.append("    --")
        methods = cls.methods
        if public_only:
            methods = [m for m in methods if m.visibility.value == "public"]
        for method in methods:
            if method.name.startswith("__") and method.name != "__init__":
                if public_only:
                    continue
            lines.append(f"    {method.plantuml_signature()}")
        lines.append("}")

        # Note docstring si existe
        if cls.docstring and not public_only:
            # première ligne seulement
            first_line = cls.docstring.strip().split("\n")[0][:80]
            lines.append(f"note top of {cls.name}")
            lines.append(f"  {first_line}")
            lines.append("end note")

    # Relations
    for rel in relations:
        src = rel.source.split(".")[-1]
        tgt = rel.target.split(".")[-1]
        # vérifier existence
        class_names = {c.name for c in sorted_classes}
        if src not in class_names or tgt not in class_names:
            continue

        if rel.relation_type == RelationType.INHERITANCE:
            lines.append(f"{tgt} <|-- {src}")
        elif rel.relation_type == RelationType.COMPOSITION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"{src} *-- {tgt}{label}")
        elif rel.relation_type == RelationType.AGGREGATION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"{src} o-- {tgt}{label}")
        elif rel.relation_type == RelationType.ASSOCIATION:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"{src} --> {tgt}{label}")
        elif rel.relation_type == RelationType.DEPENDENCY:
            label = f" : {rel.label}" if rel.label else ""
            lines.append(f"{src} ..> {tgt}{label}")

    lines.append("@enduml")
    return "\n".join(lines)


def generate_module_class_diagram_plantuml(
    module_name: str,
    classes: list["ClassInfo"],
    all_relations: list["RelationInfo"],
    public_only: bool = False,
) -> str:
    """Diagramme PlantUML pour un module."""

    class_map = {c.qualified_name: c for c in classes}
    module_class_names = {c.name for c in classes}
    relevant_relations = []
    for rel in all_relations:
        src_simple = rel.source.split(".")[-1]
        tgt_simple = rel.target.split(".")[-1]
        if src_simple in module_class_names and tgt_simple in module_class_names:
            relevant_relations.append(rel)
        elif src_simple in module_class_names and rel.relation_type == RelationType.INHERITANCE:
            relevant_relations.append(rel)
        elif tgt_simple in module_class_names and rel.relation_type == RelationType.INHERITANCE:
            relevant_relations.append(rel)

    extended = dict(class_map)
    for rel in relevant_relations:
        if rel.target not in extended:
            from ..analyzer.models import ClassInfo
            from pathlib import Path

            stub = ClassInfo(name=rel.target.split(".")[-1], module="external", file_path=Path("."))
            extended[rel.target] = stub
        if rel.source not in extended:
            from ..analyzer.models import ClassInfo
            from pathlib import Path

            stub = ClassInfo(name=rel.source.split(".")[-1], module="external", file_path=Path("."))
            extended[rel.source] = stub

    return generate_class_diagram_plantuml(
        extended, relevant_relations, public_only=public_only, title=f"Module {module_name}"
    )
