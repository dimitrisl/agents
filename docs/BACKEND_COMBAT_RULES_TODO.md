# Backend TODO — Combat rules data

Written alongside the client-side refactor of the player sheet's **Combat & Inventory**
tab (`client/src/app/features/player/tabs/combat-panel/`). That work needed level-scaled
class dice — Sneak Attack `5d6` for a level 10 Rogue, the Monk's Martial Arts die, Rage
damage, superiority dice. None of it could come from the backend, so it currently lives in
`client/src/app/core/data/class-combat.data.ts`.

This file records exactly what is missing and what has to happen for that table to move
back behind the API, where it belongs.

---

## 1. The class JSONs have prose, not tables

`data/rules/classes/{2014,2024}/*.json` store `progression.<level>.features[]` as
`{ name, description }`. The descriptions *reference* scaling tables that were never
transcribed. From `2014/rogue.json`, level 1:

> "you can deal an extra **1d6** damage … The amount of the extra damage increases as you
> gain levels in this class, **as shown in the Sneak Attack column of the Rogue table**."

There is no Sneak Attack column anywhere in the file. A scan of every class in both
editions for dice notation returns only the base die:

| Edition | Class     | Level | Feature         | Dice found in text |
|---------|-----------|-------|-----------------|--------------------|
| 2014    | rogue     | 1     | Sneak Attack    | `1d6` only         |
| 2014    | monk      | 1     | Martial Arts    | `d4` only          |
| 2014    | barbarian | —     | Rage            | none (prose only)  |
| 2014    | paladin   | 2     | Divine Smite    | `1d8 2d8 5d8`      |
| 2024    | barbarian | 9/13/17 | Brutal Strike | `1d10 2d10 3d10`   |

Two classes encode the progression in the **feature name** instead
(`Bardic Inspiration (d8)`, `Brutal Critical (2 dice)`, `Song of Rest (d10)`), which is not
machine-readable without string parsing, and the 2024 Bard is incomplete — it has only the
L1 `d6` and L15 `d12` entries, missing `d8` at 5 and `d10` at 10.

### Proposed shape

Add a sibling to `progression` in each class file:

```jsonc
{
  "class_name": "Rogue",
  "scaling": {
    "sneak_attack": {
      "name": "Sneak Attack",
      "kind": "rider",              // rider | attack | heal | defense | utility
      "damage_type": null,
      "hint": "Once per turn, with Advantage or an ally within 5 ft.",
      "steps": [                     // highest level <= character level wins
        { "level": 1,  "notation": "1d6"  },
        { "level": 3,  "notation": "2d6"  },
        { "level": 5,  "notation": "3d6"  }
        // … through level 19
      ]
    }
  }
}
```

`kind` and `hint` are what the client renders; keep them here so the UI copy stays with the
rules rather than in the frontend. Mirror the enum in
`client/src/app/core/data/class-combat.data.ts` (`CombatActionKind`).

**Classes needing `scaling` blocks** (see the client table for the values already worked
out): rogue, monk, barbarian, paladin, fighter, bard, ranger, warlock, cleric, druid,
artificer. Sorcerer and wizard need nothing beyond the shared cantrip tier.

### Values that are not plain steps

Three cases don't fit `steps[]` and need their own fields:

- **Barbarian Brutal Critical** (2014, L9/13/17) adds 1–3 *weapon* damage dice on a crit.
  The die size comes from the weapon, not the class. Client field: `extraCritDice`.
- **Fighter Champion Improved Critical** (L3/15) lowers the crit threshold to 19 then 18.
  Client field: `critThreshold`.
- **Paladin Divine Smite** scales with the *spell slot spent*, not with level; the client
  offers one option per slot the character has unlocked. Client field: `options[]`.

## 2. No endpoint serves class progression

`RulesRepository.get_class_progression()` / `.get_features_at_level()` exist and are cached,
but nothing exposes them. `server/routers/rules_router.py` only has the AI-backed
`/rules/query`, `/rules/compare`, `/rules/validate` and `/rules/autofix`.

Needed:

```
GET /rules/classes                      → list of class names for an edition
GET /rules/classes/{class_name}         → hit_die, caster_type, progression, scaling
GET /rules/classes/{class_name}/scaling?level=10
      → the resolved actions for that level, ready to render
```

The last one is what the client actually wants — resolving `steps[]` server-side keeps the
"highest step wins" rule in one place. Query param `edition` defaulting to `EDITION_2014`,
consistent with the rest of the repository API.

Once this lands, `ClassCombatService.getProfile()` swaps its call to
`resolveClassActions()` for an HTTP call. Nothing else in the client moves — that is why
the data file is kept free of Angular imports.

## 3. Orphaned rules files

`data/rules/weapons.json` (31 weapons: `name`, `category`, `damage`, `properties[]`,
`mastery`, `weight`, `cost`) and `data/rules/weapon_masteries_2024.json` (8 masteries with
full descriptions) are **read by no backend code at all**. Confirmed by grepping the whole
Python tree — only `items.json` is loaded, in `RulesRepository.get_all_items()`.

Meanwhile `stats_service.py` hardcodes weapon knowledge in several places:

- `calculate_weapon_stats()` (line ~411) infers ranged/finesse from substrings of the
  weapon name: `["bow", "crossbow", "sling", "dart"]` and
  `["rapier", "dagger", "scimitar", "shortsword"]`. `weapons.json` has a real
  `properties[]` array with `Finesse`, `Thrown`, `Two-Handed`, `Ammunition`.
- `sync_character_stats()` (lines ~962–1007) hardcodes four mastery pairings
  (`Sap (Longsword)`, `Slow (Light Crossbow)`, `Graze (Greatsword)`,
  `Topple (Warhammer)`) that `weapons.json` already declares per weapon via `mastery`.

Worth wiring `weapons.json` into `RulesRepository` and replacing both substring heuristics.
That would also let the player sheet show real property chips and mastery tooltips —
deliberately left out of the current client work, which uses only the fields already stored
on `char.weapons[]`.

## 4. Dice parity

`backend/services/dice_service.py::roll_dice` accepts a single `NdX+M` expression.
The client now also rolls **compound** damage — weapon plus every active rider, with
critical hits doubling dice but not flat modifiers, and Brutal Critical's own dice excluded
from that doubling (`DiceService.rollDamage`, `DamagePart.noCrit`).

Its parser is also more lenient than the backend's, because it has to read what the backend
itself writes: `rebuild_damage_formula` produces `1d8 + 4 slashing`, which the strict
`^(\d*)d(\d+)([+-]\d+)?$` regex rejects.

If dice ever need to roll server-side (shared rolls over the websocket, DM-visible rolls,
anti-cheat), port `rollDamage` and the lenient parser to keep the two in step. Right now
all rolling is client-side, so this is not urgent.

## 5. Subclass features are absent entirely

The class JSONs contain no subclass data — `constants.py` has only the *names*
(`SUBCLASSES_2014`, `SUBCLASSES_2024`). The client therefore hardcodes the three subclass
dice that matter most in combat:

- Fighter / Battle Master — superiority die `d8` → `d10` (10th) → `d12` (18th)
- Fighter / Champion — Improved Critical
- Ranger / Hunter — Colossus Slayer `1d8`
- Artificer / Battle Smith — Arcane Jolt `2d6` → `4d6` (15th)

Missing as a result: Cleric domain Divine Strike damage *types*, Monk subclass dice,
Rogue Assassin, Barbarian path features, Warlock invocations. A `subclasses` section in the
class files — or `data/rules/subclasses/{edition}/{class}.json` — would cover these and
would also improve the level-up analysis in `forge_service.py`.
