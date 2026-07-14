"""Builder de site MkDocs avec diagrammes."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from jinja2 import Template

if TYPE_CHECKING:
    from ..analyzer.models import PackageInfo
    from ..config import GendocConfig

from ..renderers import (
    generate_class_diagram_mermaid,
    generate_class_diagram_plantuml,
    generate_class_diagram_svg,
    generate_module_class_diagram_mermaid,
    generate_module_class_diagram_plantuml,
    generate_package_diagram_mermaid,
    generate_package_diagram_plantuml,
    generate_package_diagram_svg,
    generate_package_summary_markdown,
    save_svg,
    try_convert_svg_to_png,
)

from ..analyzer.relationships import get_focused_subgraph


MKDOCS_YML_TEMPLATE = """site_name: {{ site_name }}
{% if repo_url %}repo_url: {{ repo_url }}{% endif %}
theme:
  name: {{ theme }}
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - content.code.copy
    - toc.follow

markdown_extensions:
  - toc:
      permalink: true
  - admonition
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.highlight
  - pymdownx.inlinehilite
  - pymdownx.snippets

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          paths: {{ python_paths }}
          options:
            docstring_style: google
            show_source: true
            show_root_heading: true
            show_root_full_path: false
            show_object_full_path: false
            heading_level: 2
            separate_signature: true

nav:
  - Accueil: index.md
  - Packages: packages.md
{% if focus_class %}
  - Focus {{ focus_class }}: focus.md
{% endif %}
  - Modules:
{% for mod in modules %}
    - {{ mod.display }}: {{ mod.file }}
{% endfor %}
  - API:
{% for mod in modules %}
    - {{ mod.display }}: api/{{ mod.api_file }}
{% endfor %}
  - Diagrammes:
    - Package Mermaid: diagrams/package.mmd
    - Package PlantUML: diagrams/package.puml
"""

INDEX_MD_TEMPLATE = """# {{ package_name }} - Documentation

> Généré automatiquement par **gendoc** le {{ date }}

## Vue d'ensemble

- **Modules :** {{ modules_count }}
- **Classes :** {{ classes_count }}
- **Relations :** {{ relations_count }}

{% if circular %}
!!! warning "Dépendances circulaires détectées"
    Le projet contient {{ circular|length }} cycle(s) de dépendances circulaires :

    {% for cycle in circular %}
    - `{{ " -> ".join(cycle) }}`
    {% endfor %}
{% endif %}

## Diagramme de packages

Structure et dépendances internes (circulaires en rouge).

```mermaid
{{ package_mermaid }}
```

![Package SVG](diagrams/package.svg)

## Diagrammes de classes

### Diagramme global

```mermaid
{{ class_mermaid }}
```

## Navigation

- [Structure détaillée des packages](packages.md)
- [Modules](modules/)
- [API Reference](api/)

---

*Documentation générée avec gendoc - 100% local, open-source*
"""

PACKAGES_MD_TEMPLATE = """# Packages - {{ package_name }}

{{ summary }}

## Diagramme de dépendances (Mermaid)

```mermaid
{{ package_mermaid }}
```

## Diagramme de dépendances (PlantUML)

```plantuml
{{ package_plantuml }}
```

## SVG

![Package dependencies](diagrams/package.svg)
"""


MODULE_MD_TEMPLATE = """# Module `{{ module.dotted_path }}`

> Fichier: `{{ module.file_path }}`

## Classes ({{ module.classes|length }})

{% for cls in module.classes %}
- **{{ cls.name }}** {% if cls.bases %} (hérite de {{ ", ".join(cls.bases) }}) {% endif %}
{% endfor %}

## Diagramme de classes

```mermaid
{{ mermaid_diagram }}
```

![Diagram](diagrams/{{ module.name }}.svg)

### PlantUML

```plantuml
{{ plantuml_diagram }}
```

## Détails API

Voir [API {{ module.dotted_path }}](../api/{{ api_file }})

## Imports

- **Internes :** {{ ", ".join(module.internal_imports) if module.internal_imports else "aucun" }}
- **Externes :** {{ ", ".join(module.external_imports[:10]) if module.external_imports else "aucun" }}

## Code source

```python
# {{ module.file_path }}
```
"""


API_MODULE_TEMPLATE = """# API - {{ module.dotted_path }}

{% for cls in module.classes %}
## {{ cls.name }}

::: {{ module.dotted_path }}.{{ cls.name }}
    options:
        show_source: true
        heading_level: 3

{% endfor %}
"""

FOCUS_MD_TEMPLATE = """# Focus : {{ focus_class }} (profondeur {{ depth }})

Diagramme centré sur **{{ focus_class }}** et ses {{ depth }} niveaux de collaborateurs.

```mermaid
{{ mermaid }}
```

![Focus SVG](diagrams/focus_{{ focus_class }}.svg)

```plantuml
{{ plantuml }}
```

## Classes incluses

{% for cls in classes %}
- `{{ cls.qualified_name }}` - {{ cls.docstring.splitlines()[0] if cls.docstring else "" }}
{% endfor %}
"""


class SiteBuilder:
    """Construit le site de documentation."""

    def __init__(self, config: "GendocConfig", package_info: "PackageInfo"):
        self.config = config
        self.package_info = package_info
        self.start_time = time.time()

    def build(self) -> Path:
        """Construit le site complet et retourne chemin vers docs dir."""

        # Déterminer docs_dir et output_dir toujours résolus par rapport à CWD ou config absolue
        def resolve(p: Path) -> Path:
            if p.is_absolute():
                return p
            return (Path.cwd() / p).resolve()

        output_dir = resolve(self.config.output_dir)
        docs_src = resolve(self.config.docs_dir)

        # Si docs_src est dans un sous-dossier qui n'existe pas, créer
        docs_src.mkdir(parents=True, exist_ok=True)

        # Créer sous-dossiers
        (docs_src / "diagrams").mkdir(exist_ok=True)
        (docs_src / "modules").mkdir(exist_ok=True)
        (docs_src / "api").mkdir(exist_ok=True)

        # Générer diagrammes package
        self._generate_package_diagrams(docs_src)

        # Générer diagrammes par module et pages
        self._generate_module_pages(docs_src)

        # Générer pages API
        self._generate_api_pages(docs_src)

        # Générer index.md
        self._generate_index(docs_src)

        # Générer packages.md
        self._generate_packages_page(docs_src)

        # Générer focus si demandé
        if self.config.focus_class:
            self._generate_focus_page(docs_src)

        # Générer mkdocs.yml
        self._generate_mkdocs_yml(docs_src)

        return docs_src

    def _generate_package_diagrams(self, docs_src: Path) -> None:
        """Génère diagrammes package."""

        mermaid = generate_package_diagram_mermaid(self.package_info)
        plantuml = generate_package_diagram_plantuml(self.package_info)
        svg = generate_package_diagram_svg(self.package_info)

        diagrams_dir = docs_src / "diagrams"

        # Toujours générer mmd et puml (éditable)
        (diagrams_dir / "package.mmd").write_text(mermaid, encoding="utf-8")
        (diagrams_dir / "package.puml").write_text(plantuml, encoding="utf-8")

        if "svg" in self.config.formats:
            save_svg(svg, diagrams_dir / "package.svg")
            # PNG
            if "png" in self.config.formats:
                try_convert_svg_to_png(diagrams_dir / "package.svg", diagrams_dir / "package.png")

    def _generate_module_pages(self, docs_src: Path) -> None:
        """Génère pages modules + diagrammes."""

        for dotted, mod_info in sorted(self.package_info.modules.items()):
            display = dotted.split(".")[-1]
            safe_name = dotted.replace(".", "_")

            # Diagrammes
            try:
                mermaid = generate_module_class_diagram_mermaid(
                    dotted,
                    mod_info.classes,
                    self.package_info.relations,
                    public_only=self.config.public_only,
                )
                plantuml = generate_module_class_diagram_plantuml(
                    dotted,
                    mod_info.classes,
                    self.package_info.relations,
                    public_only=self.config.public_only,
                )
            except Exception:
                mermaid = f"classDiagram\n    %% Erreur génération pour {dotted}\n    class {display}"
                plantuml = f"@startuml\nclass {display}\n@enduml"

            # SVG pour ce module
            classes_map = {c.qualified_name: c for c in mod_info.classes}
            # Ajouter relations internes
            rels = [
                r
                for r in self.package_info.relations
                if r.source.split(".")[-1] in {c.name for c in mod_info.classes}
                or r.target.split(".")[-1] in {c.name for c in mod_info.classes}
            ]
            # filtrer pour avoir seulement classes du module + relations internes
            # mais pour SVG on garde que classes du module pour lisibilité
            svg_content = generate_class_diagram_svg(
                classes_map, [r for r in rels if r.source in classes_map and r.target in classes_map], title=dotted
            )

            # Sauver diagrammes
            diag_dir = docs_src / "diagrams"
            (diag_dir / f"{safe_name}.mmd").write_text(mermaid, encoding="utf-8")
            (diag_dir / f"{safe_name}.puml").write_text(plantuml, encoding="utf-8")
            if "svg" in self.config.formats:
                save_svg(svg_content, diag_dir / f"{safe_name}.svg")
                if "png" in self.config.formats:
                    try_convert_svg_to_png(diag_dir / f"{safe_name}.svg", diag_dir / f"{safe_name}.png")

            # Page module markdown
            tmpl = Template(MODULE_MD_TEMPLATE)
            api_file = f"{safe_name}.md"

            # mod_info for template needs dict-like
            module_dict = {
                "dotted_path": dotted,
                "file_path": mod_info.file_path,
                "classes": mod_info.classes,
                "name": display,
                "internal_imports": mod_info.internal_imports,
                "external_imports": mod_info.external_imports,
            }

            content = tmpl.render(
                module=module_dict,
                mermaid_diagram=mermaid,
                plantuml_diagram=plantuml,
                api_file=api_file,
            )

            (docs_src / "modules" / f"{safe_name}.md").write_text(content, encoding="utf-8")

    def _generate_api_pages(self, docs_src: Path) -> None:
        for dotted, mod_info in sorted(self.package_info.modules.items()):
            safe_name = dotted.replace(".", "_")
            tmpl = Template(API_MODULE_TEMPLATE)
            content = tmpl.render(module=mod_info, dotted_path=dotted)
            (docs_src / "api" / f"{safe_name}.md").write_text(content, encoding="utf-8")

    def _generate_index(self, docs_src: Path) -> None:
        # Diagrammes globaux
        global_classes = self.package_info.classes
        global_relations = self.package_info.relations

        try:
            class_mermaid = generate_class_diagram_mermaid(
                global_classes, global_relations, public_only=self.config.public_only
            )
        except Exception as e:
            class_mermaid = f"classDiagram\n    %% Erreur: {e}"

        package_mermaid = generate_package_diagram_mermaid(self.package_info)

        tmpl = Template(INDEX_MD_TEMPLATE)
        from datetime import datetime

        content = tmpl.render(
            package_name=self.package_info.name,
            date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            modules_count=len(self.package_info.modules),
            classes_count=len(self.package_info.classes),
            relations_count=len(self.package_info.relations),
            circular=self.package_info.circular_dependencies,
            package_mermaid=package_mermaid,
            class_mermaid=class_mermaid,
        )
        (docs_src / "index.md").write_text(content, encoding="utf-8")

    def _generate_packages_page(self, docs_src: Path) -> None:
        summary = generate_package_summary_markdown(self.package_info)
        mermaid = generate_package_diagram_mermaid(self.package_info)
        plantuml = generate_package_diagram_plantuml(self.package_info)

        tmpl = Template(PACKAGES_MD_TEMPLATE)
        content = tmpl.render(
            package_name=self.package_info.name,
            summary=summary,
            package_mermaid=mermaid,
            package_plantuml=plantuml,
        )
        (docs_src / "packages.md").write_text(content, encoding="utf-8")

    def _generate_focus_page(self, docs_src: Path) -> None:
        focus = self.config.focus_class
        depth = self.config.focus_depth
        if not focus:
            return

        try:
            focused_classes, focused_relations = get_focused_subgraph(
                self.package_info.classes, self.package_info.relations, focus, depth
            )
        except ValueError as e:
            # écrire page erreur
            (docs_src / "focus.md").write_text(f"# Erreur focus\n\n{e}\n", encoding="utf-8")
            return

        mermaid = generate_class_diagram_mermaid(focused_classes, focused_relations, public_only=self.config.public_only, title=f"Focus {focus}")
        plantuml = generate_class_diagram_plantuml(focused_classes, focused_relations, public_only=self.config.public_only, title=f"Focus {focus}")
        svg = generate_class_diagram_svg(focused_classes, focused_relations, title=f"Focus {focus}")

        diag_dir = docs_src / "diagrams"
        (diag_dir / f"focus_{focus}.mmd").write_text(mermaid, encoding="utf-8")
        (diag_dir / f"focus_{focus}.puml").write_text(plantuml, encoding="utf-8")
        save_svg(svg, diag_dir / f"focus_{focus}.svg")
        if "png" in self.config.formats:
            try_convert_svg_to_png(diag_dir / f"focus_{focus}.svg", diag_dir / f"focus_{focus}.png")

        tmpl = Template(FOCUS_MD_TEMPLATE)
        content = tmpl.render(focus_class=focus, depth=depth, mermaid=mermaid, plantuml=plantuml, classes=focused_classes.values())
        (docs_src / "focus.md").write_text(content, encoding="utf-8")

    def _generate_mkdocs_yml(self, docs_src: Path) -> None:
        # Générer mkdocs.yml à la racine du projet (parent de docs)
        # On suppose mkdocs.yml à côté de docs, ou dans cwd
        # Pour simplicité: générer dans cwd et aussi dans docs parent

        modules = []
        for dotted in sorted(self.package_info.modules.keys()):
            safe = dotted.replace(".", "_")
            modules.append(
                {
                    "display": dotted,
                    "file": f"modules/{safe}.md",
                    "api_file": f"{safe}.md",
                }
            )

        # Construire liste de chemins Python pour mkdocstrings
        # Utiliser chemins relatifs pour portabilité
        python_paths = []
        cwd = Path.cwd()
        python_paths.append(".")
        # Parent du package (relatif à cwd si possible)
        try:
            pkg_parent = self.package_info.root_path.parent.resolve()
            # rendre relatif à cwd
            try:
                rel = pkg_parent.relative_to(cwd)
                python_paths.append(str(rel))
            except ValueError:
                # si pas sous cwd, garder absolu ou nom
                python_paths.append(str(pkg_parent))
        except Exception:
            pass
        # root_path lui-même si pertinent
        try:
            root_path = self.package_info.root_path.resolve()
            try:
                rel_root = root_path.relative_to(cwd)
                if str(rel_root) != ".":
                    python_paths.append(str(rel_root))
            except ValueError:
                pass
        except Exception:
            pass
        # Ajouter src si existe
        src_path = cwd / "src"
        if src_path.exists():
            python_paths.append("src")
        example_path = cwd / "example"
        if example_path.exists():
            python_paths.append("example")
        # Dédoublonner en gardant ordre
        seen = set()
        deduped = []
        for p in python_paths:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        python_paths = deduped

        tmpl = Template(MKDOCS_YML_TEMPLATE)
        content = tmpl.render(
            site_name=self.config.site_name,
            theme=self.config.theme,
            repo_url=self.config.repo_url,
            modules=modules,
            focus_class=self.config.focus_class,
            python_paths=python_paths,
        )

        # Déterminer où écrire mkdocs.yml
        # Si docs_src est ./docs, mkdocs.yml doit être à ./mkdocs.yml
        mkdocs_path = docs_src.parent / "mkdocs.yml"
        # Si docs_src est dans package_path, on le met à parent de package_path ?
        # Ecrire dans CWD aussi
        cwd_mkdocs = Path.cwd() / "mkdocs.yml"

        # Ecrire dans both si nécessaire, mais prioritaire docs_src.parent
        mkdocs_path.write_text(content, encoding="utf-8")
        if mkdocs_path.resolve() != cwd_mkdocs.resolve():
            # Copier aussi dans cwd si on est en mode build depuis ailleurs ?
            # On n'écrase pas si existe déjà avec autre contenu ? On écrase
            try:
                cwd_mkdocs.write_text(content, encoding="utf-8")
            except Exception:
                pass
