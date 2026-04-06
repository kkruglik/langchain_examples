```mermaid
flowchart LR
    User([User])
    Writer[Writer]
    Editor[Editor]
    Factchecker[Factchecker]

    User --> Writer
    Writer --> Editor
    Editor -->|approve| Factchecker
    Editor -->|reject| Writer
    Factchecker -->|approve| User
    Factchecker -->|reject| Writer
```
