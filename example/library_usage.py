"""Exemples d'utilisation de gendoc comme librairie Python.

Ce fichier montre comment intégrer gendoc dans vos propres scripts,
sans passer par la CLI.

Installation:
    pip install -e .  # depuis la racine du projet gendoc
"""

import tempfile
from pathlib import Path

import gendoc

# Les sorties de démonstration vont dans un dossier temporaire,
# pas dans votre projet.
OUT = Path(tempfile.mkdtemp(prefix="gendoc_demo_"))

# ------------------------------------------------------------
# 1. Analyse simple
# ------------------------------------------------------------
print("=== 1. Analyse simple ===")
pkg = gendoc.analyze_package("./example/example_pkg")
print(f"Package: {pkg.name}")
print(f"Modules: {len(pkg.modules)}")
print(f"Classes: {len(pkg.classes)}")
print(f"Relations: {len(pkg.relations)}")
print(f"Circular: {pkg.circular_dependencies}")

# Avec API haut niveau
print("\n=== 1b. Quick overview ===")
print(gendoc.quick_overview("./example/example_pkg"))

# ------------------------------------------------------------
# 2. Vérification CI (analysable ?)
# ------------------------------------------------------------
print("\n=== 2. Check analysable ===")
is_ok = gendoc.check_package("./example/example_pkg")
print(f"Analysable: {is_ok}")

# ------------------------------------------------------------
# 3. Génération diagrammes en mémoire (sans fichiers)
# ------------------------------------------------------------
print("\n=== 3. Diagrammes en mémoire ===")
diagrams = gendoc.get_diagrams("./example/example_pkg", diagram_format="mermaid")
print("Package diagram Mermaid (extrait):")
print(diagrams["package"][:500])

print("\nClasses globales Mermaid (extrait):")
print(diagrams["classes"][:500])

# Focus sur une classe
print("\n=== 3b. Focus Order depth 2 ===")
focus_diags = gendoc.get_diagrams(
    "./example/example_pkg", diagram_format="mermaid", focus_class="Order", depth=2
)
print(focus_diags["focus_Order"][:800])

# ------------------------------------------------------------
# 4. Génération site complet (comme CLI `gendoc build`)
# ------------------------------------------------------------
print("\n=== 4. Build docs site ===")
docs_path = gendoc.build_docs(
    "./example/example_pkg",
    output_dir=OUT / "site_lib",
    docs_dir=OUT / "docs_lib",
    formats=["mmd", "puml", "svg"],
    site_name="Demo lib usage",
)
print(f"Docs générés dans: {docs_path}")
print(f"Fichiers: {list(docs_path.glob('*.md'))[:3]}")
print(f"Diagrams: {list((docs_path / 'diagrams').glob('*.mmd'))[:3]}")

# ------------------------------------------------------------
# 5. Usage avancé avec config objet
# ------------------------------------------------------------
print("\n=== 5. Usage avancé avec GendocConfig ===")
cfg = gendoc.GendocConfig(
    package_path="./example/example_pkg",  # str accepté, converti en Path
    package_name="example_pkg",
    output_dir=OUT / "site_advanced",
    docs_dir=OUT / "docs_advanced",
    formats=["mmd", "svg"],
    public_only=True,  # uniquement membres publics
    focus_class="OrderService",
    focus_depth=1,
    site_name="Advanced Demo",
)
docs_path2 = gendoc.build_docs_with_config(cfg)
print(f"Advanced docs: {docs_path2}")

# ------------------------------------------------------------
# 6. Analyse détaillée des relations
# ------------------------------------------------------------
print("\n=== 6. Relations détaillées ===")
from gendoc.analyzer.models import RelationType

for rel in pkg.relations:
    if rel.relation_type == RelationType.INHERITANCE:
        print(f"Héritage: {rel.source} -> {rel.target}")
    elif rel.relation_type == RelationType.COMPOSITION:
        print(f"Composition: {rel.source} *-- {rel.target} ({rel.label})")

# ------------------------------------------------------------
# 7. Intégration dans votre propre outil
# ------------------------------------------------------------
print("\n=== 7. Exemple intégration ===")


def my_custom_doc_generator(package_path: str):
    """Votre propre générateur qui utilise gendoc comme brique."""
    pkg = gendoc.analyze(package_path, include_private=False)

    # Votre logique custom
    report = {
        "total_classes": len(pkg.classes),
        "total_modules": len(pkg.modules),
        "circular_deps": pkg.circular_dependencies,
        "classes_by_module": {
            mod: [c.name for c in info.classes] for mod, info in pkg.modules.items()
        },
    }
    return report


report = my_custom_doc_generator("./example/example_pkg")
import json

print(json.dumps(report, indent=2, ensure_ascii=False))
