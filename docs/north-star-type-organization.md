# Superseded Type Organization Note

This document has been superseded by `docs/data-driven-pathway-big-bang-refactor.md` and the implemented pathway-centric runtime.

The current boundary is:

```text
pathway JSON -> graph composer -> typed graph -> generic compiler -> generic simulator -> UI/API
```

Production code no longer owns pathway-specific state enums, scenario enums, structured-claim routes, or global parameter catalogs. Pathway-specific IDs and biology live in `data/pathways/*.json`.
