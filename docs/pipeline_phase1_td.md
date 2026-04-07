```mermaid
flowchart TD
    User(User) -->|brief| Writer[Writer]
    Writer -->|draft| Editor[Editor]
    Editor -->|approve| Factchecker[Factchecker]
    Editor -->|reject + feedback| Writer
    Factchecker -->|final script| User
    Factchecker -->|reject + feedback| Writer

    Writer -.->|calls| Scraper[(Scraper)]
    Editor -.->|calls| LengthCheck[(Length Check)]

    style User fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style Writer fill:#7B68EE,stroke:#5A4DB0,color:#fff
    style Editor fill:#F5A623,stroke:#C47D0E,color:#fff
    style Factchecker fill:#E74C3C,stroke:#A93226,color:#fff
    style Scraper fill:#ECF0F1,stroke:#95A5A6,color:#333
    style LengthCheck fill:#ECF0F1,stroke:#95A5A6,color:#333
```

