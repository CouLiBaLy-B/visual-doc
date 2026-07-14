# Module `example_pkg.services`

> Fichier: `/home/user/visual-doc/example/example_pkg/services.py`

## Classes (2)


- **UserService** 

- **OrderService** 


## Diagramme de classes

```mermaid
classDiagram
    %% Module example_pkg.services
    class OrderService {
        +user_service UserService
        +orders List[Order]
        +products List[Product]
        --
        +__init__(user_service: UserService)
        +add_product(product: Product) None
        +create_order(user_id: int) Order
        +get_order_summary(order: Order) str
        +process_payment(order: Order) bool
    }
    class UserService {
        +users List[User]
        #_cache dict[int, User]
        --
        +__init__()
        +create_user(email: str, name: str) User
        +find_by_email(email: str) Optional[User]
        +list_users() List[User]
    }
    OrderService *-- UserService : user_service
```

![Diagram](diagrams/services.svg)

### PlantUML

```plantuml
@startuml
title Module example_pkg.services
skinparam classAttributeIconSize 0
skinparam classFontStyle bold
hide empty members
class OrderService {
    + user_service : UserService
    + orders : List[Order]
    + products : List[Product]
    --
    + __init__(user_service: UserService)
    + add_product(product: Product) : None
    + create_order(user_id: int) : Order
    + get_order_summary(order: Order) : str
    + process_payment(order: Order) : bool
}
note top of OrderService
  Service gestion commandes - Dépend de UserService et Product.
end note
class UserService {
    + users : List[User]
    # _cache : dict[int, User]
    --
    + __init__()
    + create_user(email: str, name: str) : User
    + find_by_email(email: str) : Optional[User]
    + list_users() : List[User]
}
note top of UserService
  Service gestion utilisateurs.
end note
OrderService *-- UserService : user_service
@enduml
```

## Détails API

Voir [API example_pkg.services](../api/example_pkg_services.md)

## Imports

- **Internes :** .models, .utils
- **Externes :** __future__, typing

## Code source

```python
# /home/user/visual-doc/example/example_pkg/services.py
```