# DM Workspace — Index των tickets

Τα tickets ζουν πλέον στο **[GitHub Issues](https://github.com/dimitrisl/agents/issues)** —
εκεί είναι η πηγή αλήθειας. Αυτό το αρχείο είναι μόνο ο χάρτης.

Πηγή: [notes - todos/DM_WORKSPACE_ANALYSIS.md](notes%20-%20todos/DM_WORKSPACE_ANALYSIS.md)

---

## 🔥 P0 — Security

Κοινή ρίζα: το `campaign_name` είναι primary key και **κανένα** endpoint δεν ελέγχει `owner_id`.

| # | Ticket | Est |
|---|---|---|
| [#13](https://github.com/dimitrisl/agents/issues/13) | Campaign endpoints have no ownership checks | M |
| [#14](https://github.com/dimitrisl/agents/issues/14) | `GET /campaigns/` leaks DM notes to players | S |
| [#15](https://github.com/dimitrisl/agents/issues/15) | `GET /{name}/messages` returns every whisper to every user | M |
| [#16](https://github.com/dimitrisl/agents/issues/16) | `POST /campaigns/join` can move another user's character | S |

## 🔴 P1 — Σπασμένη λειτουργικότητα

| # | Ticket | Est |
|---|---|---|
| [#12](https://github.com/dimitrisl/agents/issues/12) | Session Prep tab never shows a result | **XS** ⭐ |
| [#17](https://github.com/dimitrisl/agents/issues/17) | Add Member modal writes nothing to the server | L |
| [#18](https://github.com/dimitrisl/agents/issues/18) | Party HP and conditions are never persisted or broadcast | L |
| [#19](https://github.com/dimitrisl/agents/issues/19) | `activeTurnIndex` is never clamped | S |
| [#20](https://github.com/dimitrisl/agents/issues/20) | Remove fake demo data fallbacks | M |

## 🟡 P2

| # | Ticket | Est |
|---|---|---|
| [#21](https://github.com/dimitrisl/agents/issues/21) | `copyInviteCode()` copies a hardcoded fake code | XS |
| [#22](https://github.com/dimitrisl/agents/issues/22) | `is_secret` announces the secret instead of hiding it | M |
| [#23](https://github.com/dimitrisl/agents/issues/23) | Inconsistent `encodeURIComponent` on campaign names | XS |
| [#24](https://github.com/dimitrisl/agents/issues/24) | Initiative tracker has no rounds, no persistence | L |
| [#25](https://github.com/dimitrisl/agents/issues/25) | Players never see whose turn it is | M |
| [#26](https://github.com/dimitrisl/agents/issues/26) | Player has no agency over how they roll | M |
| [#27](https://github.com/dimitrisl/agents/issues/27) | No way to delete a campaign or remove a member | M |
| [#28](https://github.com/dimitrisl/agents/issues/28) | Whispers/roll requests grow unbounded in one Mongo doc | L |
| [#29](https://github.com/dimitrisl/agents/issues/29) | `generateEncounter()` ignores the actual party | S |

## 🔵 P3

| # | Ticket | Est |
|---|---|---|
| [#32](https://github.com/dimitrisl/agents/issues/32) | Small DM workspace cleanups | S |
| [#33](https://github.com/dimitrisl/agents/issues/33) | Hardcoded `'2014 Edition'` in three places | S |
| [#34](https://github.com/dimitrisl/agents/issues/34) | Decide the fate of the unused `/dm/riddle` | XS |
| [#35](https://github.com/dimitrisl/agents/issues/35) | No presence indicator for connected players | M |

---

## Εξαρτήσεις

```
#13 (ownership) ──┬──> #17 (add member)
                  └──> #27 (delete/kick)

#19 (clamping) ──> #24 (rounds) ──> #25 (turn broadcast)

#18 (HP persist) ──> #25 (ίδιο κανάλι: party_update)

#15 (messages filter) ──> #22 (is_secret)

#33 (edition) ──> #29 (encounter)
```

## Προτεινόμενο πρώτο sprint

| Σειρά | Ticket | Γιατί |
|---|---|---|
| 1 | **#12** | XS, ξεκλειδώνει ολόκληρο tab — γρήγορη νίκη |
| 2 | **#21**, **#23** | XS, καθαρίζουν αμηχανίες |
| 3 | **#19** | Το πιο ορατό bug στο τραπέζι |
| 4 | **#14**, **#16** | Τα δύο μικρότερα security — ξεκινάει η δουλειά authz |
| 5 | **#20** | Καθαρίζει τα demo φαντάσματα πριν χτιστεί τίποτα από πάνω |

> **#17** και **#18** είναι τα πιο πολύτιμα αλλά θέλουν backend — άρα άρση του περιορισμού
> στο `client/CLAUDE.md` ή ξεχωριστό backend πέρασμα.

## Labels που δημιουργήθηκαν

`security` · `tech-debt` · `area:frontend` · `area:backend` · `P0` · `P1` · `P2` · `P3`
(συν τα υπάρχοντα `bug` και `enhancement`)
