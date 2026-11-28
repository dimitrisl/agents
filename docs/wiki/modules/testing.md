# 🧪 Subsystem: Testing Architecture (`tests/` & `server/tests/`)

## 📌 Overview
The automated test suite combines unit tests, service tests, integration tests with `mongomock`, and route API tests using FastAPI `TestClient`.

---

## 🏗️ Structure & Test Categories

```
tests/
├── e2e/                              # Opaque-box requirement & integration suites (test_github_issues.py, test_qa_audit_defects.py, test_tabletop_workflows.py, tier 1-4)
├── fixtures/                         # Mock JSON payloads for rules, campaigns, and characters
├── test_unique_indexes_and_races.py # Unique index collisions, race conditions (register, campaign, join)
├── test_integration.py               # Full-flow integration, character takeover protection, party isolation
├── test_vtt_security.py              # Token security, atomic updates, and hidden token redaction
├── test_websocket_channel.py         # Real-time WebSocket connection manager and channel isolation
├── test_campaign_roll_log.py         # Campaign sheet roll persistence, 2014/2024 parity, multi-character & homonym isolation (#197)
├── test_loot_distribution.py         # Per-item loot recipient_id routing, currency split, and item_recipient_id compatibility (#222)
├── test_board_consolidation_fixes.py # Board consolidation & QA regressions across 2014/2024 exhaustion/long-rest rules, campaign security guards, VTT/encounter/journey redaction, mixed-case invite codes, and asset URL encoding
├── test_dm_exhaustion_locks_modifiers.py # 2014 & 2024 Exhaustion L0-6 & L6 death, bypass waiver, non-destructive Athas magic suppression, signed DM modifiers, campaign-only locks & 1-shot unlocks vs Solo freedom, _roll_in_secret Disadvantage/cancellation, and campaign detach/delete cleanup
├── test_deterministic_character_math.py # Multi-class (Fighter, Wizard, Rogue, Draconic Sorcerer) Level 3 & 8 2014/2024 deterministic math, Forge/Level-Up anti-hallucination, PDF bounds, and SRD encounter hydration/fallback
├── test_code_review_fixes.py         # Full-stack security & correctness regression suite (XFF right-to-left proxy IP, magic-byte image validation, production JWT enforcement, VTT fog bounds, rules parity, level-up server authority, safe script queries)
├── test_2014_qa_fixes.py             # 2014 Edition QA regression & 2024 parity suite (Paladin/Monk/Rogue/Artificer saves, Resilient half-feat, weapon profs, feat prereqs, all 13 subclass progressions & domain/innate spells, 2014 choice pickers + Agonizing Blast, Sorcerous Restoration & racial resource pools, senses/resistances/save advantages)
├── test_2024_rules_parity.py         # Ticket #259 2024 Revision parity suite (all 13 subclass mechanics JSONs & bonus_spells validation, Divine Order / Primal Order proficiencies & Thaumaturge/Magician skill bonuses, College of Dance/Valor Bard, 2024 vs 2014 structured level-up & Manual Forge choices, /rules/weapon-masteries, /rules/class-choices, and /rules/combat-profile)
├── test_items_and_magic_mechanics_260.py # Ticket #260 SRD items.json expansion & deterministic magic item mechanics (*Bracers of Defense*, *Robe of the Archmagi*, *Stone of Good Luck*, *Wand/Rod/Amulet/Staff* spell atk/DC, *Bracers of Archery*, *Sentinel Shield*, *Belts of Giant Strength*, Athas suppression)
├── test_spellcasting_and_short_rest_261.py # Ticket #261 Prepared Spells Cap (2014 vs 2024 & multiclass), Always-Prepared split separation, Ritual JSON tags, Natural Recovery edition gating, and Arcane/Natural Recovery + Harness Divine Power /short-rest API & validation
├── test_multiclass_level_up_264.py  # Ticket #264 Multiclass 13+ prerequisite enforcement (current & new classes), 2014 vs 2024 PHB Level 1 proficiency grants (armor, weapons, tools, Bard instrument & bonus skill pickers, saving-throw lock), primary subclass isolation, lowercase class canonicalization, and /forge/level-up-analysis & /forge/level-up-apply HTTP 400 guards & persistence
├── test_auth_lifecycle.py            # Ticket #266 Self-service /change-password (PBKDF2, demo exclusion, token_version revocation across HTTP/WS, rate limit), Admin one-time /reset-password (RBAC, self/admin/demo guards, forced change lock), and optional Discord OAuth2 (503/hidden gating, CSRF state+cookie, single-use #code exchange, verified email linking)
├── test_pwa_and_health_267.py        # Ticket #267 GET /api/v1/health (200/503 without secret leakage + @limiter.exempt), PWA manifest/PNG icons & ngsw-config rules-only dataGroup safety invariants, and Docker/Nginx production configuration checks
├── test_inventory_encumbrance_262.py # Ticket #262 Ammunition schema coercion (0 vs None), string/fraction weapon & catalog weight resolution, coin weight (50/lb), Bag of Holding stashing, 2014/2024 Carrying Capacity (Powerful Build, Brawny, Bear Aspect), and /characters CRUD + Athas suppression tests
├── test_story_scenes_288.py        # Ticket #288 Story Scenes card URL safety, 2014/2024 DM CRUD & RBAC isolation, targeted WS reveal/dismiss routing without dm_notes leak, entity-shared asset orphan preservation, and campaign cascade deletion
├── test_conditions_and_defenses_275.py # Ticket #275 Condition mechanics (2014 vs 2024 Invisible Init ADV & Incapacitated Init DIS, AUTO-FAIL STR/DEX short-circuiting), advisory Blindsight/Truesight countermeasures, non-destructive speed=0 locks & GET hydration preserving base_speed, Purity of Body vs Self-Restoration & Nature's Ward / Aura of Courage / Brave / Stout Resilience / Fey Ancestry antidotes & defenses, and secret DM roll mode integration
├── test_mechanics*.py                # AC math, spell slots, saving throws, and conditions
├── test_dnd_rules_audit_fixes*.py    # 2014 vs. 2024 rule audit verifications
├── test_audit_critical_p0_p1_fixes.py # Regression suite for 17 code review & security audit fixes
├── test_schemas.py                   # Pydantic boundary validation
└── ...                               # Unit tests for dice, PDF, forge, sessions, and encounters

server/tests/
├── test_api.py                       # REST API route integration tests
└── test_lore.py                      # Rules query and lore prompt tests

client/src/
└── app/**/*.spec.ts                  # Angular 19 / Jest unit & component tests (core/rules, state services, DM VTT, Forge, Player Desktop & Mobile Companion views)
```

---

## 📐 Invariants & Mocks
1. **No External Network Calls:** Tests must never make live network calls to Gemini or external databases. Use `unittest.mock.patch` for AI client calls and `mongomock` for MongoDB operations.
2. **Deterministic Parallel Reproducibility:** Tests execute in parallel across CPU cores via `pytest-xdist` (`addopts = "-n auto --dist worksteal"` in [`pyproject.toml`](../../../pyproject.toml)). Every test must isolate shared state (such as `CONFIG_FILE` via `tmp_path` + `monkeypatch`) and pass deterministically (`poetry run pytest tests/ -v`, or `-n 0` for single-process debugging).
3. **Tabletop & Online QA Simulation:** Multi-client integration is verified via `scripts/qa/simulate_session.py` across both In-Person Mobile Companion (`< 1024px`) and Online VTT Desktop (`>= 1024px`) modes (`poetry run python scripts/qa/simulate_session.py --mode both`).
