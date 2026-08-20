---
name: page-refactor
description: The procedure for redesigning or restyling a page/feature in the Angular client so it conforms to design-contract.md. Use when asked to refactor, restyle, redesign, align to the design system, clean up the UI, or migrate a feature to the forge-* kit. Covers the audit, the presentation-only boundary, and the definition of done. Not for bug fixes or behaviour changes.
---

# Page refactor

The repeatable process behind `client/ui-refactor/00-overview.md` … `20-*.md`.
Twenty of these have been done by hand; this is that procedure.

**The authority is `client/design-contract.md`, not this file.** This file is the order of
operations. Read the contract in full at step 1 — do not work from memory of it.

---

## The one boundary that matters

**Presentation only.**

Do not change services, routes, state, event names, `@Input()`/`@Output()` names, HTTP
calls, WebSocket wiring, or dice/rules logic. A refactored page must be a drop-in
replacement — the parent component and every consumer keep working untouched.

If the page has a real behavioural bug, **report it, do not fix it inline.** It becomes a
separate task. Mixing a redesign with a behaviour change makes the diff unreviewable and
hides regressions.

Also load the `angular19-tailwind4` skill — it covers the stack traps (Tailwind v4 has no
config file; OnPush needs reference replacement).

---

## Step 1 — Read before touching

1. `client/design-contract.md` in full. §1 tokens, §2 the kit, §3 patterns, §4 a11y,
   §5 responsive, §6 known debt, §7 done.
2. The target feature: every `.ts`, `.html`, `.css` in its folder.
3. The reference implementation for the pattern you need — `features/player/` is the
   canonical one, named per pattern in §3.

## Step 2 — Audit and report before editing

Produce a short list of what actually violates the contract:

```bash
cd client/src/app/features/<target>
grep -rn "text-body-sm\|bg-black/\|bg-white/\|phyrexian-\|nav-tabs\|tab-item\|modal-card" .
grep -rn "#[0-9a-fA-F]\{3,6\}\|rgba(" . --include=*.html --include=*.css
grep -rn "<button\|<input\|<select\|<textarea" . --include=*.html   # should be forge-*
grep -rn "variant=\"pill\"" .
```

Report: literal colors, hand-rolled controls, legacy classes, ad-hoc surfaces, missing
a11y attributes, `min-w-0` gaps. **If the page needs a pattern the kit does not have, stop
and report it** so it is added to the kit once — never improvise a local version.

## Step 3 — Apply, in this order

1. **Structure** — page shell (`forge-page`), card/section skeleton, grid per §3.
2. **Kit substitution** — every raw `<button>` → `[forgeButton]`, every form control →
   `[forgeInput]`/`[forgeSelect]`/`[forgeTextarea]`, dialogs → `<forge-modal>`, empty lists →
   `<forge-empty-state>`, tabs → `<forge-tabs variant="underline">`.
3. **Tokens** — replace every literal color and ad-hoc surface with §1 tokens.
4. **A11y** — §4 in full: focus rings, `aria-*`, real interactive elements, never
   color-alone meaning.
5. **Responsive** — §5: `min-w-0` on text-bearing flex/grid children, stacking rules.
6. **Legacy** — remove every §6 class the touched files still reference. If a legacy rule in
   `styles.css` has lost its last consumer, delete the rule too.

Split large components: container keeps state, panels/modals become dumb presentational
children (see `features/dm/`).

## Step 4 — Verify

```bash
cd client && npm run build
cd client && npm test
```

`npm test` runs Jest, but the suite is nearly empty and a page refactor is presentation-only —
it will not catch a styling regression. Never claim tests pass without running them.

Then walk `design-contract.md` §7 explicitly, item by item:

1. Only §1 tokens — zero literal colors, zero arbitrary spacing
2. Only §2 kit components
3. §3 patterns reused, not reinvented
4. §4 and §5 met in full
5. Zero §6 legacy classes left in touched files
6. `npm run build` passes
7. Edition toggle recolors correctly — check **both** 2014 and 2024
8. All bindings, outputs, services, routes and logic unchanged

Widths to check: **375 / 768 / 1024 / 1440 / 1920**, no horizontal page overflow at any.

## Step 5 — Report

State explicitly:

- **what was preserved** — bindings, outputs, services, routes, logic (this is the part the
  user actually needs to trust)
- what changed, grouped by the §7 items
- any contract gap found (missing kit pattern, missing token)
- any behavioural bug spotted and deliberately **not** fixed
