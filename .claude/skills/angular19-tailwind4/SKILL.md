---
name: angular19-tailwind4
description: Stack-specific corrections for this repo's Angular 19.2 + Tailwind v4 client. Load BEFORE writing or editing any Angular component, template, service, or CSS under client/. Covers where common defaults are wrong here - Tailwind v4 is CSS-first with no config file, components are standalone with OnPush, templates use @if/@for, and state lives in signals inside services. Triggers on: creating a component, styling anything, adding a Tailwind utility or token, touching styles.css, editing a template, wiring state.
---

# Angular 19.2 + Tailwind v4 — this repo

Your defaults are calibrated on older versions of both. This file is the correction.
Everything below was verified against the code in `client/`.

---

## 1. Tailwind v4 — CSS-first. This is the highest-risk area.

**There is no `tailwind.config.js`, there never was, and creating one is forbidden.**
Configuration lives in `client/src/styles.css` (319 lines).

```
@layer theme, base, legacy, components, utilities;
@import "tailwindcss";      /* NOT the v3 @tailwind base/components/utilities */

:root { --bg-deep: #09090c; ... }   /* raw CSS variables */
@theme inline { --color-accent: var(--theme-accent); ... }  /* exposes them as utilities */
```

### Adding a token

❌ **Wrong** (v3 instinct):
```js
// tailwind.config.js — this file must not exist
module.exports = { theme: { extend: { colors: { accent: '#d93b48' } } } };
```

✅ **Right** — two steps in `styles.css`:
```css
:root      { --my-token: #abc123; }         /* 1. declare */
@theme inline { --color-mine: var(--my-token); }  /* 2. expose → enables bg-mine, text-mine */
```

The naming prefix decides the utility family: `--color-*` → `bg-/text-/border-`,
`--text-*` → font sizes, `--radius-*` → `rounded-*`.

> **Before adding a token, stop.** The design contract says never invent one. Check
> `design-contract.md` §1 first — it is almost always already there under another name.

### Why this fails silently

A v3-style config is simply ignored. The utility class lands in the HTML, resolves to
nothing, and the element renders unstyled with **no build error**. If a style "does not
apply", suspect a non-existent token before suspecting specificity.

Real example of this already in the repo: `text-body-sm` is used **51 times across 20
files** but is not defined in `@theme inline`, so all 51 silently inherit their size.
(`design-contract.md` §6 — do not add new usages.)

### The accent color is edition-driven

```css
:root                  { --theme-accent: var(--primary-red); }
[data-edition="2024"]  { --theme-accent: var(--accent-violet); }
```

Never hardcode the accent. Use `text-accent` / `bg-accent` / `border-accent` so the edition
toggle recolors the page. Any new page must be checked in **both** editions.

---

## 2. Angular 19 — but match the codebase, not the changelog

| Your instinct | This repo | Why |
|---|---|---|
| `NgModule`, `declarations` | **standalone: true**, always | no NgModule exists anywhere |
| `*ngIf` / `*ngFor` | **`@if` / `@for`** in new templates | 19 files migrated, 29 not — see below |
| `constructor(private x: X)` | **keep constructor injection** | only 5 files use `inject()`; consistency wins |
| `BehaviorSubject` for shared state | **signals, in services** | `auth.service`, `character-state.service` |
| default change detection | **`ChangeDetectionStrategy.OnPush`** | 52 of 67 components already |

### The migration rule

29 files still use `*ngIf`. **Migrate only inside a file you are already editing for another
reason.** Never open a standalone migration sweep — it produces huge unreviewable diffs
across features you were not asked to touch.

The same rule applies to `inject()` and signals: do not convert existing components as a
side quest.

### Component skeleton

```ts
@Component({
  selector: 'app-thing-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ForgeButtonDirective],  // from '../../shared/ui'
  templateUrl: './thing-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ThingPanelComponent {
  @Input() value = '';
  @Output() valueChange = new EventEmitter<string>();
  @Output() save = new EventEmitter<void>();
}
```

### Container / presentational split — mandatory

The feature root owns **all** state, HTTP and WebSocket wiring. Panels and modals are dumb:
`@Input()` in, `@Output()` out, **no injected services**.

Reference: `features/dm/dm.component.ts` (container) with its `panels/` and `modals/`.

An `@Input()` + `@Output() xChange` pair enables `[(x)]` banana-in-a-box from the parent —
that is the established two-way pattern here, not `ngModel` reaching into a child.

### OnPush and mutation

With OnPush, mutating an array in place does not repaint. Replace the reference:

```ts
this.items = [...this.items, next];       // ✅ repaints
this.items.push(next);                    // ❌ silently stale
```

---

## 3. Things that are easy to get wrong here

- **Import the UI kit from the barrel:** `from '../../shared/ui'`. Never deep paths.
- **Never hand-roll a button, input, select, textarea, badge, tab or modal.** Use the
  `forge-*` kit. Missing pattern → stop and report, do not improvise.
- **`encodeURIComponent()` every campaign name** used in a URL — they contain spaces and are
  path segments. Several existing calls forget this; do not copy them.
- **Shared interfaces belong in `core/models/`**, not exported from a component.
- **No new dependencies** without asking.

---

## 4. Verifying

```bash
cd client && npm run build
```

**There is no test framework in this project** — no `test` script, no Karma, no Jasmine, no
spec files. The build is the only automated gate. Never report that tests pass. For visual
work, confirm against `design-contract.md` §7 and check both editions.
