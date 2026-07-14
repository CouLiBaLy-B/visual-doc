# example_pkg - Documentation

> Généré automatiquement par **gendoc** le 2026-07-14 12:23

## Vue d'ensemble

- **Modules :** 6
- **Classes :** 10
- **Relations :** 13


!!! warning "Dépendances circulaires détectées"
    Le projet contient 1 cycle(s) de dépendances circulaires :

    
    - `example_pkg.circular_a -> example_pkg.circular_b -> example_pkg.circular_a`
    


## Diagramme de packages

Structure et dépendances internes (circulaires en rouge).

```mermaid
flowchart TD
    example_pkg[example_pkg]
    example_pkg_circular_a[circular_a]
    example_pkg_circular_b[circular_b]
    example_pkg_models[models]
    example_pkg_services[services]
    example_pkg_utils[utils]

    example_pkg --> example_pkg_models
    example_pkg --> example_pkg_utils
    example_pkg --> example_pkg_services
    example_pkg_services --> example_pkg_models
    example_pkg_services --> example_pkg_utils
    example_pkg_circular_a -->|circular| example_pkg_circular_b
    example_pkg_circular_b -->|circular| example_pkg_circular_a

    style example_pkg_circular_a fill:#ffcccc,stroke:#ff0000,stroke-width:2px
    style example_pkg_circular_b fill:#ffcccc,stroke:#ff0000,stroke-width:2px
    linkStyle 5 stroke:#ff0000,stroke-width:2px
    linkStyle 6 stroke:#ff0000,stroke-width:2px
```

![Package SVG](diagrams/package.svg)

## Diagrammes de classes

### Diagramme global

```mermaid
classDiagram
    class CacheManager {
        +max_size int
        #_store dict[str, object]
        --
        +__init__(max_size: int)
        +get(key: str) object | None
        +set(key: str, value: object) None
        +clear() None
    }
    class Order {
        +id int
        +user User
        +items List[OrderItem]
        +status str
        +created_at datetime
        --
        +add_item(product: Product, quantity: int) OrderItem
        +total_amount() float
        +set_status(new_status: str) None
    }
    class OrderItem {
        +product Product
        +quantity int
        --
        +total() float
    }
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
    class PremiumUser {
        +membership_level str
        +bonus_points int
        #_vip_code str
        --
        +__init__(id: int, email: str, name: str, membership_level: str)
        +add_points(points: int) None
        +get_discount() float
    }
    class Product {
        +id int
        +name str
        +price float
        +stock int
        +description Optional[str]
        --
        +is_available() bool
        +apply_discount(percent: float) float
    }
    class ServiceA {
        +name str
        +b_service object | None
        --
        +__init__(name: str)
        +set_b(b_service) None
        +do_work() str
        +call_b() str
    }
    class ServiceB {
        +name str
        +a_service object | None
        --
        +__init__(name: str)
        +set_a(a_service) None
        +do_work() str
        +call_a() str
    }
    class User {
        +id int
        +email str
        +name str
        +created_at datetime
        #_password_hash str
        --
        +greet() str
        #_validate() bool
        +is_active() bool
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
    User <|-- PremiumUser
    OrderItem *-- Product : product
    Order *-- User : user
    Order o-- OrderItem : items
    Order ..> Product : add_item param
    Order ..> OrderItem : add_item return
    UserService o-- User : users
    UserService *-- User : _cache
    UserService ..> User : create_user return
    OrderService *-- UserService : user_service
    OrderService o-- Order : orders
    OrderService o-- Product : products
    OrderService ..> Order : create_order return
```

## Navigation

- [Structure détaillée des packages](packages.md)
- [Modules](modules/)
- [API Reference](api/)

---

*Documentation générée avec gendoc - 100% local, open-source*