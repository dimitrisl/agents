# Client — Angular 19 front end

D&D campaign tool. This file covers the **client only**. UI/UX rules live in
[`design-contract.md`](design-contract.md) — read it before touching any template.

---

## 1. Scope boundary — hard rule

**Work only inside `agents/client/`.**

Never edit `server/`, `backend/`, `data/`, `scripts/` or `tests/`. If a task cannot be
completed without a backend change (a missing endpoint, a wrong response key, an
authorization gap), **stop and report it** — describe the exact change needed and let the
user decide. Do not work around it with client-side hacks.

---

## 2. Stack

| | |
|---|---|
| Angular | **19.2** — standalone components, no NgModules |
| TypeScript | 5.7 |
| Styling | **Tailwind v4, CSS-first** — tokens in `src/styles.css`, **no `tailwind.config.js` exists and none may be created** |
| State | RxJS 7.8 + Angular signals (services only, see §5) |
| Extras | `@angular/cdk` (overlay/a11y), `three` + `cannon-es` (3D dice), `zone.js` (not zoneless) |
| API | `environment.apiBaseUrl = '/api/v1'` |

---

## 3. Commands

```bash
cd client
npm start        # ng serve — proxies /api and /ws to http://localhost:8000 (src/proxy.conf.json)
npm run build    # production build
```

> ⚠️ **There is no test framework in this project.** No `test` script, no Karma, no Jasmine,
> no spec files. `npm run build` is the only automated gate that exists.
> Never claim tests pass. Verify with a successful build plus the acceptance checks in
> `design-contract.md` §7.

---

## 4. Layout

```
src/app/
├─ core/
│  ├─ services/     auth · character-state · websocket · dice · roll-toast · class-combat
│  └─ models/       character · campaign · campaign-inbox · user
├─ shared/
│  ├─ ui/           the forge-* kit — import from the barrel: shared/ui
│  └─ components/   roll-toast, command palette, etc.
└─ features/        admin · auth · dm · forge · player · rules · settings
```

**Reference implementations:** `features/player/` for layout and design, `features/dm/` for
the container/presentational split.

---

## 5. Conventions in this codebase

Follow what is already here. Do not modernise code you were not asked to touch.

- **Standalone components only.** Never add an `NgModule`.
- **`ChangeDetectionStrategy.OnPush` on every new component.** 52 of 67 already use it.
- **Container / presentational split.** The feature root component owns state, HTTP and
  WebSocket wiring; panels and modals are dumb — `@Input()` in, `@Output()` out, no
  injected services. See `features/dm/dm.component.ts` and its `panels/` + `modals/`.
- **New templates use `@if` / `@for`.** 29 files still use `*ngIf`; migrate only inside files
  you are already editing. Never open a sweeping migration PR.
- **Signals live in services** (`auth.service`, `character-state.service`). Components use
  plain fields. Do not convert existing components to signals as a side quest.
- **Shared interfaces belong in `core/models/`.** `dm.component.ts` currently exports
  `PartyMember` and `InitiativeCombatant` and four files import them from there — that is
  known debt, do not copy the pattern.
- **`encodeURIComponent()` every campaign name** placed in a URL. Campaign names contain
  spaces and are used as path segments; several existing calls forget this.
- **Import the UI kit from the barrel:** `from '../../shared/ui'`, never deep paths.

---

## 6. UI/UX — `design-contract.md` is the single source of truth

Read it in full before styling anything. Its four non-negotiables:

1. **Never invent a token.** Every color, size and shadow comes from `src/styles.css`.
2. **Never invent a component.** Use the `forge-*` kit. Missing pattern → stop and report.
3. **Never hardcode the accent color** — it is edition-driven.
4. **Presentation only** — do not change services, routes, state, event names, or dice/rules logic.

§6 of that file lists known debt (`text-body-sm`, `@layer legacy`, `variant="pill"` tabs,
ad-hoc surfaces). Fix opportunistically in files you touch; **never extend it**.
§7 is the definition of done for any page work.

---

## 7. Skills

Two project skills carry the detail that does not belong in every session's context:

| Skill | Load when |
|---|---|
| `angular19-tailwind4` | writing/editing any component, template, service or CSS — stack traps where common defaults are wrong here |
| `page-refactor` | redesigning or restyling a page against `design-contract.md` |

---

## 8. Working agreement

- **Presentation-only by default.** Changing behaviour, bindings or business logic needs to
  be asked for explicitly.
- **No new dependencies** without asking first.
- **Report what you preserved**, not just what you changed — which bindings, outputs,
  services and routes are untouched.
- Deliver the whole task. If part of it is blocked (usually by §1), finish everything else
  and say plainly what was left out and why.
