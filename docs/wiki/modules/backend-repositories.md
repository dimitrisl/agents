# 📚 Subsystem: Backend Repositories (`backend/repositories/`)

## 📌 Overview
The `backend/repositories/` package encapsulates data access for static D&D rule definitions stored in `data/rules/`. It abstracts raw file access behind an in-memory cached repository.

---

## 🔑 Key Repositories

| Repository | Responsibility |
| :--- | :--- |
| [`rules_repository.py`](../../../backend/repositories/rules_repository.py) | Singleton `RulesRepository` providing access to 2014 & 2024 D&D rulesets: classes, subclasses, spells, feats, backgrounds (`get_background_data`), species/races (`get_race_data`), items, weapons, skills, and languages. Implements module-level caches to prevent accidental state mutation. |
| [`character_repository.py`](../../../backend/repositories/character_repository.py) | Abstraction interface for character persistence. |

---

## 📐 Invariants
1. **Immutable Cached Returns:** Methods returning sets or complex structures return `frozenset` or deep copies to prevent caller mutation from corrupting the in-memory rules cache.
2. **Edition Isolation:** Every lookup method accepts an `edition` argument (`EDITION_2014` or `EDITION_2024`) to guarantee correct mechanics.
