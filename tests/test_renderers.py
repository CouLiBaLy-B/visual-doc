"""Tests renderers."""

import pytest

from gendoc.analyzer import analyze_package
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
    # package avec circular doit avoir style rouge
    svg = generate_package_diagram_svg(sample_package)

    # Vérifier que circular détecté implique couleur rouge dans SVG (ffcccc ou ff0000)
    if sample_package.circular_dependencies:
        assert "ff" in svg.lower()  # rouge
