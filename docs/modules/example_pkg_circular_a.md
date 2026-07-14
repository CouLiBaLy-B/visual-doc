# Module `example_pkg.circular_a`

> Fichier: `/home/user/visual-doc/example/example_pkg/circular_a.py`

## Classes (1)


- **ServiceA** 


## Diagramme de classes

```mermaid
classDiagram
    %% Module example_pkg.circular_a
    class ServiceA {
        +name str
        +b_service object | None
        --
        +__init__(name: str)
        +set_b(b_service) None
        +do_work() str
        +call_b() str
    }
```

![Diagram](diagrams/circular_a.svg)

### PlantUML

```plantuml
@startuml
title Module example_pkg.circular_a
skinparam classAttributeIconSize 0
skinparam classFontStyle bold
hide empty members
class ServiceA {
    + name : str
    + b_service : object | None
    --
    + __init__(name: str)
    + set_b(b_service) : None
    + do_work() : str
    + call_b() : str
}
note top of ServiceA
  Service A qui dépend de B.
end note
@enduml
```

## Détails API

Voir [API example_pkg.circular_a](../api/example_pkg_circular_a.md)

## Imports

- **Internes :** .circular_b, circular_b
- **Externes :** __future__

## Code source

```python
# /home/user/visual-doc/example/example_pkg/circular_a.py
```