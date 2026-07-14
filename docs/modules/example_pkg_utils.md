# Module `example_pkg.utils`

> Fichier: `/home/user/visual-doc/example/example_pkg/utils.py`

## Classes (1)


- **CacheManager** 


## Diagramme de classes

```mermaid
classDiagram
    %% Module example_pkg.utils
    class CacheManager {
        +max_size int
        #_store dict[str, object]
        --
        +__init__(max_size: int)
        +get(key: str) object | None
        +set(key: str, value: object) None
        +clear() None
    }
```

![Diagram](diagrams/utils.svg)

### PlantUML

```plantuml
@startuml
title Module example_pkg.utils
skinparam classAttributeIconSize 0
skinparam classFontStyle bold
hide empty members
class CacheManager {
    + max_size : int
    # _store : dict[str, object]
    --
    + __init__(max_size: int)
    + get(key: str) : object | None
    + set(key: str, value: object) : None
    + clear() : None
}
note top of CacheManager
  Gestionnaire cache simple.
end note
@enduml
```

## Détails API

Voir [API example_pkg.utils](../api/example_pkg_utils.md)

## Imports

- **Internes :** aucun
- **Externes :** __future__, re, typing

## Code source

```python
# /home/user/visual-doc/example/example_pkg/utils.py
```