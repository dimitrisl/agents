# 21 — Design contract

**This file is the single source of truth for the UI. Paste it into every page-refactor prompt.**

It is extracted from the code as it exists after the Player Dashboard redesign (`20-player-dashboard-mockup-alignment.md`). The Player Dashboard is the reference implementation — when this document is ambiguous, look at `client/src/app/features/player/`.

Rules for anyone (human or agent) applying this contract:

1. **Never invent a token.** Every color, font size and shadow comes from `client/src/styles.css`. If you need something that is not here, **stop and report it** instead of adding an arbitrary value.
2. **Never invent a component.** Use the `forge-*` kit below. If a page needs a pattern the kit does not have, **stop and report it** so it can be added to the kit once, not five times.
3. **Never hardcode the accent color.** It is edition-driven (see §1.2).
4. Presentation only. Do not change services, routes, state, event names, or dice/rules logic.

---

## 1. Tokens — `client/src/styles.css`

Tailwind is **v4, CSS-first**. There is **no `tailwind.config.js`** and none may be created. Tokens are CSS variables in `:root`, exposed as utilities through `@theme inline`.

### 1.1 Colors

| Utility | Variable | Value | Use for |
|---|---|---|---|
| `bg-deep` | `--bg-deep` | `#09090c` | page background |
| `bg-surface` | `--bg-card` | `rgba(15,15,19,.92)` | top-level cards (`forge-card`) |
| `bg-panel` | `--bg-panel` | `rgba(18,17,22,.72)` | inner panel inside a card |
| `bg-tile` | `--bg-tile` | `rgba(23,22,27,.70)` | smallest surface: stat tiles, group headers, chips |
| `bg-surface-hover` | `--bg-card-hover` | `rgba(22,22,28,.96)` | hover on an interactive surface |
| `border-hairline` | `--border-card` | `rgba(255,255,255,.07)` | every neutral border |
| `border-hairline-hover` | `--border-card-hover` | accent @ 34% | hover border on interactive cards |
| `text-ink` | `--text-primary` | `#f2f2f5` | primary text, values |
| `text-muted` | `--text-muted` | `#8e8ea3` | labels, secondary text, inactive |
| `text-gold` / `bg-gold` | `--text-gold` | `#d9b355` | **proficiency / expertise only** |
| `text-accent` / `bg-accent` / `border-accent` | `--theme-accent` | edition-driven | primary action, HP, key stat values |
| `text-red` | `--primary-red` | `#d93b48` | fixed red (semantic danger), **not** the accent |
| `text-violet` | `--accent-violet` | `#a855f7` | fixed violet |
| `text-cobalt` | `--accent-cobalt` | `#0a84ff` | info |
| `text-emerald` | `--accent-emerald` | `#2ecc71` | success |

### 1.2 The accent is edition-driven — non-negotiable

```css
:root                  { --theme-accent: var(--primary-red); }   /* 2014 → crimson */
[data-edition="2024"]  { --theme-accent: var(--accent-violet); } /* 2024 → violet  */
```

- Always use `text-accent` / `bg-accent` / `border-accent`, or `var(--theme-accent)` / `color-mix(in srgb, var(--theme-accent) N%, transparent)` in CSS.
- **Never** write `#d93b48`, `#ff4b4b`, `text-red-500`, or any literal crimson in a template.
- Gold is **not** edition-driven and is reserved for proficiency semantics. Do not use gold as a generic highlight.
- After any visual change, toggle the edition switch and confirm the whole screen recolors.

### 1.3 Surface hierarchy

Exactly four levels. Separate them by **background step**, not by giving everything a border.

```
bg-deep                 page
  └─ bg-surface         forge-card                (1 border-hairline)
       └─ bg-panel      inner panel / list body   (usually borderless)
            └─ bg-tile  stat tile / group header / chip
```

Do not nest a bordered box inside a bordered box. Inside a card, use `divide-y divide-hairline/70` between sections instead of wrapping each section in a border.

### 1.4 Typography

| Utility | Size | Font | Use for |
|---|---|---|---|
| `text-display` | 1.75rem | `font-display` (Cinzel) | page `h1` |
| `text-title` | 1.125rem | `font-display` | card / section headings |
| `text-metric` | 1.5rem | `font-sans`, bold | stat values, HP, scores |
| `text-body` | .9375rem | `font-sans` | body copy, buttons, skill names |
| `text-label` | .75rem | `font-sans` | control labels, modifiers |
| `text-micro` | .6875rem | `font-sans`, uppercase, `text-muted` | tile labels, section eyebrows |

- `font-display` (Cinzel) **only** for: page title, character name, ability-group names, card headings. Everything else is `font-sans` (Outfit).
- Uppercase only on `text-micro` labels.
- Two escape hatches exist in the reference implementation and are allowed where a value must dominate: `text-[2rem]` (HP current, page `h1`) and `text-[1.25rem]` (ability score). Do not add more.

### 1.5 Spacing, radius, motion

- Spacing: **4 / 8 / 12 / 16 / 24 / 32 px** only (`gap-1 gap-2 gap-3 gap-4 gap-6 gap-8`). No arbitrary spacing.
- Radius: cards `rounded-[14px]` (via `forge-card`) · inner panels & tiles `rounded-xl` · buttons/inputs `rounded-lg` · pills & segmented controls `rounded-full` · chips `rounded-md`.
- Transitions **120–200ms**. Movement on press ≤1px. No scale animations. Large static cards do **not** lift on hover (`[hoverable]="false"`).
- Shadows: `shadow-card` on top-level cards only. Never on rows or tiles.

---

## 2. The `forge-*` kit — `client/src/app/shared/ui/` (barrel: `index.ts`)

Use these. Do not re-implement them with raw Tailwind.

| Component | Key inputs | Notes |
|---|---|---|
| `<forge-shell>` | `hasSidebar`, `mobileTitle` · slots `[brand] [nav] [user]` | app frame; static sidebar at `lg+`, off-canvas drawer below with focus trap |
| `<forge-page>` | `title`, `subtitle` · slot `[actions]` | page container, `max-w-[1600px]`, `gap-6`. Pass **no** title when the page renders its own header |
| `<forge-card>` | `padding: none\|sm\|md\|lg`, `tone: default\|accent`, `hoverable` | `tone="accent"` = crimson-tinted border + soft glow, for the hero/primary card of a page |
| `<forge-section>` | `title`, `variant`, `density` · slot `[actions]` | titled block, optionally wrapped in a card |
| `<forge-tabs>` | `tabs`, `activeId`, `instanceId`, **`variant: 'pill' \| 'underline'`** | `underline` is the current design. `pill` is legacy — **migrate pages to `underline`**. Full roving-tabindex keyboard support built in |
| `<forge-modal>` | — | every dialog goes through this |
| `<forge-badge>` | `tone: accent\|muted\|gold\|danger\|success`, `size`, `interactive` | modifiers, editions, statuses |
| `<forge-toggle>` | `checked`, `checkedChange`, `ariaLabel` | `role="switch"`, knob left = off |
| `<forge-stat-box>`, `<forge-metric-strip>`, `<forge-metric>` | — | pre-existing stat primitives |
| `<forge-empty-state>` | `icon`, `title`, `description` | every empty list |
| `<forge-toolbar>` | `collapseAt` | responsive action row |
| `[forgeButton]` | `variant: primary\|secondary\|ghost\|danger`, `size: sm\|md\|lg`, `tone="accent"`, `iconOnly`, `fullWidth` | **the only way to style a button** |
| `[forgeInput]` `[forgeSelect]` `[forgeTextarea]` | — | the only way to style form controls |

### 2.1 Button hierarchy

One `variant="primary"` per screen — the single dominant action. Everything else is `secondary` (neutral) or `ghost` (utility). `variant="secondary" tone="accent"` marks a *distinct but not dominant* action (e.g. Level Up). `danger` is destructive only.

Sizes: `md` (≥40px) for header/primary actions, `sm` for dense rows and footers, `iconOnly` only with an `aria-label`.

---

## 3. Established patterns (copy these, do not redesign them)

Reference files under `client/src/app/features/player/`.

**Page header** — `player-dashboard-header/`
Eyebrow (`text-micro uppercase text-accent`) → `h1` (`font-display`) → one muted description line. Actions right-aligned: one `primary`, the rest `secondary`. A bottom `border-b border-hairline pb-4` separates it from content.

**Two-column dashboard** — `player.component.html`
`grid grid-cols-1 gap-6 xl:grid-cols-[340px_minmax(0,1fr)]`. The narrow column is `xl:sticky xl:top-6 xl:max-h-[calc(100vh-6rem)] xl:self-start xl:overflow-y-auto`; it stacks normally below `xl`. Both columns carry `min-w-0`.

**Workspace card** — `forge-card padding="none"` containing: a `border-b border-hairline p-4` control row (tabs left, secondary control right) → `p-4` content → sticky footer.

**Stat tile group** — `combat-stat-grid/`
One `rounded-xl bg-tile` container split by `border-x` / `border-t` dividers — **not** separate boxed tiles. Each cell: `text-micro uppercase text-muted` label over a `text-metric font-bold text-accent` value.

**Interactive row** — `skill-roll-row/`
One `grid min-h-11 ... bg-panel px-4 py-2 hover:bg-tile` row, never several small bordered boxes. Rows are separated by the parent's `divide-y divide-hairline`. Emphasised state = tinted background at ~6% + stronger text + a shape change (filled vs hollow icon), **never a saturated fill**.

**Collapsible group** — `ability-skill-group/`
`rounded-xl border border-hairline bg-panel` wrapper; header on `bg-tile` with `aria-expanded` + `aria-controls`; a rotating inline-SVG chevron (`transition-transform duration-150`). Secondary actions inside the header call `$event.stopPropagation()` so they do not toggle the group.

**Segmented control** — `roll-mode-selector/`
`grid grid-cols-N rounded-full border border-hairline bg-panel p-1`. Selected = `bg-tile text-ink font-semibold` (neutral) or a ~12–14% semantic tint. **Never a solid white or solid accent fill.** Radio inputs stay `sr-only`; `aria-checked` on each label; `title` explains the effect.

**Sticky action footer** — `action-dock/`
`sticky bottom-0 border-t border-hairline bg-surface/95 backdrop-blur-lg` with `[padding-bottom:calc(0.75rem+env(safe-area-inset-bottom))]`. Actions grouped under `text-micro uppercase` labels, groups separated by `sm:border-l sm:pl-6`.

**Sidebar nav** — `shared/components/navbar/navbar.component.css`
`.nav-link` is `min-height: 2.75rem`, fixed `1.25rem` icon slot, `border-radius: .625rem`. Active = `color-mix(--theme-accent 10%)` background + accent text + a 3px `::before` left indicator. Never a full bright border.

---

## 4. Interaction & accessibility — mandatory

- Real `<button>` / `<a>` elements. No clickable `<div>` without `role`, `tabindex` and Enter/Space handlers.
- Visible `focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-deep` on **every** interactive element.
- `aria-label` on icon-only controls · `aria-expanded` + `aria-controls` on collapsibles · `aria-selected` on tabs · `aria-checked` on switches and segmented options · `role="meter"` with `aria-valuenow/min/max` on progress bars.
- Meaning is never carried by color alone — pair it with an icon, shape or text.
- Touch targets ≥44px where layout allows; never below 28px.
- Respect `prefers-reduced-motion`.
- WCAG AA contrast. **Never place light text on a saturated gold or accent fill.**

## 5. Responsive — mandatory

Verify at **375 / 768 / 1024 / 1440 / 1920**. No horizontal page overflow at any width.

- `lg+`: sidebar static. Below `lg`: off-canvas drawer.
- `xl+`: two-column dashboards. Below: single column, narrow column first.
- Tab bars scroll horizontally with a hidden scrollbar.
- Header actions wrap or collapse into an overflow menu.
- `min-w-0` on every flex/grid child that contains text.

---

## 6. Known debt — fix opportunistically, never extend

- **`text-body-sm` does not exist.** It is used **51 times across 20 files** but there is no `--text-body-sm` in `@theme inline`, so it resolves to nothing and the text silently inherits its size. Either add the token or replace the usages with `text-body` / `text-label`. **Do not add new usages.**
- `@layer legacy` in `styles.css` still contains `.phyrexian-*`, `.nav-tabs`, `.tab-item`, `.modal-card` and a `max-width: 768px` patch block. Any page you touch must end with **zero** references to these. Delete a legacy rule once its last consumer is gone.
- `forge-tabs variant="pill"` is legacy styling. Pages still on the default must be migrated to `variant="underline"`.
- Ad-hoc surfaces (`bg-black/25`, `bg-black/30`, `bg-white/[0.04]`) still exist outside the Player Dashboard. Replace them with `bg-panel` / `bg-tile` in any file you touch.
- `features/player/ability-scores/`, `features/player/hero-vault-bar/` and `features/player/tabs/skills-panel/` are leftover directories from the refactor — verify they are unreferenced and delete them.

## 7. Definition of done for a page refactor

1. Uses only tokens from §1 — zero literal colors, zero arbitrary spacing.
2. Uses only kit components from §2 — no hand-rolled buttons, inputs, badges, tabs or modals.
3. Reuses the patterns in §3 rather than inventing equivalents.
4. Meets §4 and §5 in full.
5. Leaves no legacy class from §6 in the files it touched.
6. `cd client && npm run build` passes.
7. Edition toggle recolors the page correctly in both directions.
8. All existing bindings, outputs, services, routes and business logic are unchanged — and the report says explicitly what was preserved.
