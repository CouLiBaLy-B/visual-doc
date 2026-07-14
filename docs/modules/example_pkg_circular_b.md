# Module `example_pkg.circular_b`

> Fichier: `/home/user/visual-doc/example/example_pkg/circular_b.py`

## Classes (1)


- **ServiceB** 


## Diagramme de classes

```mermaid
classDiagram
    %% Module example_pkg.circular_b
    class ServiceB {
        +name str
        +a_service object | None
        --
        +__init__(name: str)
        +set_a(a_service) None
        +do_work() str
        +call_a() str
    }
```

![Diagram](diagrams/circular_b.svg)

### PlantUML

```plantuml
@startuml
title Module example_pkg.circular_b
skinparam classAttributeIconSize 0
skinparam classFontStyle bold
hide empty members
class ServiceB {
    + name : str
    + a_service : object | None
    --
    + __init__(name: str)
    + set_a(a_service) : None
    + do_work() : str
    + call_a() : str
}
note top of ServiceB
  Service B qui dépend de A.
end note
@enduml
```

## Détails API

Voir [API example_pkg.circular_b](../api/example_pkg_circular_b.md)

## Imports

- **Internes :** .circular_a, circular_a
- **Externes :** __future__

## Code source

```python
# /home/user/visual-doc/example/example_pkg/circular_b.py
```