# Phyrexian Forge — Angular Client

Angular 19.2 + Tailwind CSS v4 (CSS-first tokens) frontend for Phyrexian Forge.

For UI styling tokens and primitives see [`design-contract.md`](./design-contract.md), and for architecture invariants see [`../docs/wiki/modules/client-architecture.md`](../docs/wiki/modules/client-architecture.md) and [`../docs/wiki/modules/client-player.md`](../docs/wiki/modules/client-player.md).

## Common Commands
- **Dev server:** `npm start` (`http://localhost:4200`)
- **Production build:** `npm run build`
- **Unit tests (Jest):** `npm test -- --watch=false`
- **Full-stack QA & E2E (from repo root):** `poetry run python scripts/qa/simulate_session.py --mode both` and `poetry run pytest tests/e2e/ -v`
