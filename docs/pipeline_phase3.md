```mermaid
flowchart LR
    User([User])
    Researcher["Researcher\n─────────────────────\nweb search · scraper"]
    Swarm["Swarm Writers\n─────────────────────\nhumor · drama · history"]
    Writer["Writer\n─────────────────────\nscraper · web search"]
    Editor[Editor]
    Factchecker["Factchecker\n─────────────────────\nweb search"]

    User --> Researcher
    Researcher --> Swarm
    Swarm --> Writer
    Writer --> Editor
    Editor -->|approve| Factchecker
    Editor -->|reject| Writer
    Factchecker -->|approve| User
    Factchecker -->|reject| Writer
```
