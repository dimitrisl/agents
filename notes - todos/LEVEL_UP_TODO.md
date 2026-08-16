# Level Up — current state, bugs, and work required

Traced end-to-end on 2026-08-02 against the Angular client and the FastAPI backend. Every claim below cites the file and line it came from.

---

## TL;DR

Spell slots **are** recalculated on level up — the backend rebuilds them from class + level on every save. My earlier statement that they are not was wrong.

The real problem is different and worse: **the level-up modal and the apply logic read response fields that the API never returns.** New class features are silently dropped on every level up, and the modal's feature list never renders.

| Area | Status |
|---|---|
| Spell slot recalculation | ✅ works (backend, on every save) |
| HP increase | ✅ works |
| Character level increment | ✅ works |
| **New class features applied** | ❌ **broken — field name mismatch** |
| **Level-up choices (subclass, feat, spell)** | ❌ **not implemented in the Angular UI** |
| HP increase determinism | ⚠️ AI-generated, deterministic helper exists but is unused |
| Multiclassing | ❌ not supported anywhere |

---

## How it works today

1. **Analyse** — `onLevelUp()` (`client/src/app/features/player/player.component.ts:662`) posts `{ character }` to `POST /forge/level-up-analysis`.
2. **Backend analysis** — `server/routers/forge_router.py:128` → `analyze_level_up()` (`backend/services/forge_service.py:326`). It prompts the AI, merges in static class features from the rules repo, and validates against `LevelUpAnalysisSchema`.
3. **Schema returned** — `backend/core/schemas.py:322`:
   ```python
   class LevelUpAnalysisSchema(BaseModel):
       automatic_changes: List[FeatureTrait] = []
       hp_increase: int
       new_total_hp: int
       choices_required: List[LevelUpChoice] = []
       updated_proficiency_bonus: Optional[int] = None
       updated_spell_slots: Optional[Dict[str, int]] = None
   ```
4. **Apply** — `applyLevelUp()` (`player.component.ts:673`) increments `char_level`, sets `hp_max`/`hp_current`, appends features, then `PUT /characters/{id}` followed by a second save through `charState.saveCharacter()`.
5. **Backend sync on save** — both `PUT /characters/{id}` (`server/routers/character_router.py:68`) and `POST /characters` (`:41`) call `process_character_update()` (`backend/services/forge_service.py:449`), which ends in `sync_character_stats()` (`backend/services/stats_service.py:447`).
6. **Slot rebuild** — `sync_character_stats` calls `calculate_max_spell_slots(char_class, level, subclass)` (`backend/services/stats_service.py:280`, invoked at `:834`) and rebuilds `spell_slots` from scratch, preserving `used` but clamping it to the new `max` (`:836-846`).

**This is why slots are correct.** A Cleric saved at level 1 gets `{level_1: {max: 2}}`; saved at level 2 it becomes `{level_1: {max: 3}}`. Confirmed by `tests/test_mechanics_extended.py:398-448`.

---

## Bugs

### 1. New class features are never applied — CRITICAL

The API returns `automatic_changes`. The client reads `new_features`.

`player.component.ts:683`:
```ts
if (this.levelUpAnalysis.new_features) {          // always undefined
  char.features_traits = [...char.features_traits, ...this.levelUpAnalysis.new_features];
}
```

`level-up-modal.component.html:10` has the same mismatch, so the "New Class Features" block never renders — the modal shows only the HP line. Lines 20-27 additionally reference `new_spells_known` and `spell_slots_update`, neither of which exists in the schema at all, so the whole "Magical Progression" section is dead markup.

**Effect:** every level up since this schema was introduced has silently discarded the character's new features. Characters levelled through the Angular UI have incomplete `features_traits`.

**Fix (frontend):** rename to `automatic_changes` in both files, or introduce a typed `LevelUpAnalysis` interface in `core/models/` so the compiler catches this class of error. Delete the `new_spells_known` / `spell_slots_update` markup or replace it with `updated_spell_slots`.

**Also needed:** a one-off repair path for characters already levelled with missing features — `POST /rules/autofix` already runs `sync_character_stats`, but it does not restore lost features. Decide whether to backfill via a script or accept the loss.

### 2. Level-up choices are not implemented — HIGH

`LevelUpChoice` (`backend/core/schemas.py:315`) and `choices_required` exist, and `LevelUpRequest` accepts `user_choices` (used by `analyze_level_up`'s `choice_context`, `forge_service.py:333-344`). The Streamlit UI implements the full wizard (`views/player/level_up.py:432`).

The Angular client sends no `user_choices` (`player.component.ts:665`) and renders no choice UI. **A player cannot pick a subclass at level 3, an ASI/feat at level 4, or spells to learn.**

**Fix (frontend):** render `choices_required` in the level-up modal as a form (each entry has `type`, `label`, `options`, `ai_recommendation`), collect the answers, and re-run the analysis with `user_choices` before applying — mirroring the Streamlit two-pass flow.

### 3. `useSpellSlot` fabricates slots — MEDIUM

`player.component.ts:359`:
```ts
if (!char.spell_slots[key]) char.spell_slots[key] = { max: 4, used: 0 };
```
Spending a slot at a level the character does not have creates **four slots out of nothing** and persists them. The Spells tab now only renders levels with `max > 0`, so this is no longer reachable from the UI, but the code path remains.

**Fix (frontend):** return early when `getSpellSlotMax(lvl) === 0`. Never invent a `max`; it is the backend's job.

### 4. HP increase is AI-generated while a deterministic helper sits unused — MEDIUM

`hp_increase` / `new_total_hp` come from the AI response. `get_level_up_vitals()` (`backend/services/progression_service.py:35`) computes hit die and average HP gain deterministically, and is exported from `mechanics_service`, but nothing in the API path calls it — only the Streamlit wizard does (`views/player/level_up.py:52`).

**Fix (backend):** in `analyze_level_up`, compute HP with `get_level_up_vitals` and overwrite whatever the AI returned. The AI should describe features, not do arithmetic.

### 5. Level-up business logic lives in the Angular component — MEDIUM

`applyLevelUp()` composes the new character state client-side and relies on save-time sync to correct it. `process_character_update`'s own docstring says *"All calculations and data manipulation happen here, in the backend."*

It also saves twice: a raw `http.put` followed by `charState.saveCharacter()` (a `POST` upsert) — two full sync round-trips per level up, and the response of the first is discarded.

**Fix (backend):** add `POST /forge/level-up-apply` taking `{ character, analysis, user_choices }`, applying level, HP, features and choices server-side, running `sync_character_stats`, persisting, and returning the final character.
**Fix (frontend):** `applyLevelUp()` becomes a single call that sets `activeCharacter` from the response.

### 6. `updated_spell_slots` is dead weight — LOW

The schema field is `Optional[Dict[str, int]]` (flat `{"level_1": 4}`), while the character model stores `Dict[str, {max, used}]`. Nothing consumes it, and `sync_character_stats` is authoritative anyway.

**Fix:** either drop the field, or keep it strictly as a *preview* value for the modal and document that it is never written to the character.

### 7. Multiclassing is unsupported — LOW (scope decision)

`calculate_max_spell_slots(char_class, level, subclass)` takes a single class. There is no multiclass caster-level rule anywhere. If multiclassing is out of scope, say so in the docs; if not, this is a substantial rules-engine addition.

---

## Work breakdown

### Backend

- [ ] Use `get_level_up_vitals` for `hp_increase` / `new_total_hp` in `analyze_level_up`; stop trusting AI arithmetic.
- [ ] Add `POST /forge/level-up-apply` that owns the whole apply step and returns the synced, persisted character.
- [ ] Decide the fate of `updated_spell_slots` (drop, or document as preview-only).
- [ ] Confirm `choices_required` is populated for the levels that need it (subclass at class-specific levels, ASI/feat levels, spells known). Add tests.
- [ ] Consider a repair endpoint or script that re-derives missing `features_traits` for characters damaged by bug #1.

### Frontend

- [ ] Add a typed `LevelUpAnalysis` model in `client/src/app/core/models/` matching `LevelUpAnalysisSchema` exactly, and type `levelUpAnalysis` with it instead of `any` (`player.component.ts:100`). This is what would have prevented bug #1.
- [ ] Fix `applyLevelUp()` to read `automatic_changes`.
- [ ] Fix `level-up-modal.component.html` to read `automatic_changes`; remove or repoint the `new_spells_known` / `spell_slots_update` markup.
- [ ] Render `choices_required` as a form and pass `user_choices` back to the analysis endpoint.
- [ ] Guard `useSpellSlot` against levels with `max === 0`.
- [ ] Switch `applyLevelUp()` to the single new endpoint; remove the double save.
- [ ] Show a post-level-up summary (HP, prof bonus, new slots, new features) so the player can see what changed.
- [ ] Apply the design contract (`client/ui-refactor/21-design-contract.md`) to the level-up modal — it still uses `bg-black/20` and `text-body-sm`, both listed as debt in §6.

### Tests

- [ ] Cleric 1→2: `level_1` max goes 2 → 3, `used` preserved and clamped.
- [ ] Cleric 2→3: `level_2` appears with max 2.
- [ ] Warlock pact magic progression across a level up.
- [ ] Level up adds `automatic_changes` to `features_traits` (this is the regression test for bug #1).
- [ ] A level up requiring a subclass choice cannot be applied without one.
- [ ] Spending a slot at a level with `max = 0` is a no-op and persists nothing.

---

## Verification steps after the fixes

1. Create a level 1 Cleric. Spells tab shows one tile: `2 / 2`.
2. Spend one slot → `1 / 2`. Reload → still `1 / 2`.
3. Level up to 2. Confirm: level 2, HP increased, **the new feature appears in Class Features**, tile now `2 / 3` (one still spent).
4. Level up to 3. Confirm a subclass choice is requested and cannot be skipped, and that `level_2` slots appear afterwards.
5. Long rest → all slots restored to full.
6. Toggle the 2024 edition and repeat step 3 to confirm edition-specific progression still applies.
