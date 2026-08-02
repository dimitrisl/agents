# DM Workspace — Backlog για GitHub Project

Προκύπτει από το [DM_WORKSPACE_ANALYSIS.md](DM_WORKSPACE_ANALYSIS.md).
Τίτλοι στα αγγλικά (αναφέρουν κώδικα, το repo είναι αγγλικό), περιγραφές στα ελληνικά.

---

## Labels που χρειάζεσαι

| Label | Χρήση |
|---|---|
| `bug` | κάτι δεν δουλεύει όπως υπόσχεται το UI |
| `security` | διαρροή δεδομένων ή έλλειψη authorization |
| `feature` | νέα δυνατότητα |
| `tech-debt` | καθαρισμός, δεν το βλέπει ο χρήστης |
| `area:frontend` / `area:backend` | ποια πλευρά — **κρίσιμο**, το `client/CLAUDE.md` απαγορεύει backend αλλαγές σε front-end task |
| `P0`…`P3` | προτεραιότητα |

**Estimates:** XS = <30′ · S = ~2h · M = ~1 μέρα · L = 2-3 μέρες

---

# 🔥 P0 — Security (πριν βγει σε πραγματικό τραπέζι)

Και τα τέσσερα έχουν **την ίδια ρίζα**: το `campaign_name` είναι primary key και κανένα
endpoint δεν ελέγχει `owner_id`. Καλό είναι να μπουν ως ένα epic με 4 issues.

### DM-01 · Campaign endpoints have no ownership checks
`security` `area:backend` `P0` · **M**

Κανένα endpoint στο [campaign_router.py](server/routers/campaign_router.py) δεν ελέγχει αν
ο χρήστης είναι ο DM της καμπάνιας. Το `POST /campaigns/` κάνει upsert **by name**, οπότε
οποιοσδήποτε φτιάξει καμπάνια με υπάρχον όνομα σβήνει notes και party ξένης καμπάνιας.

**Acceptance**
- [ ] `POST /campaigns/`, `/{name}/notes`, `/{name}/roll-request`, `/{name}/whisper`, `/{name}/invite-code` ελέγχουν `owner_id == current_user.id` → `403` αλλιώς
- [ ] Οι παίκτες-μέλη μπορούν ακόμα να στέλνουν whisper (χρειάζονται δικό τους έλεγχο «είμαι μέλος»)
- [ ] Test: χρήστης Β δεν μπορεί να γράψει σε καμπάνια του Α

---

### DM-02 · `GET /campaigns/` leaks DM notes to players
`security` `area:backend` `P0` · **S**

Το `CampaignSchema` περιλαμβάνει `notes`, `whispers`, `roll_requests` και επιστρέφεται
ολόκληρο σε **κάθε μέλος** του party. Τα μυστικά plot hooks του DM είναι ένα devtools tab
μακριά.

**Acceptance**
- [ ] Ξεχωριστό response schema για μη-owner: χωρίς `notes`, `whispers`, `roll_requests`
- [ ] Ο owner συνεχίζει να παίρνει τα πάντα
- [ ] Test: μέλος party δεν βλέπει `notes`

---

### DM-03 · `GET /{name}/messages` returns every whisper to every user
`security` `area:backend` `P0` · **M**

Το φιλτράρισμα γίνεται **client-side** ([player.component.ts:779](client/src/app/features/player/player.component.ts#L779)).
Ο παίκτης Α διαβάζει τα ιδιωτικά whispers του DM προς τον Β με ένα `curl`.

> Το WebSocket routing είναι ήδη σωστά φτιαγμένο για ακριβώς αυτό — το REST layer το ακυρώνει.

**Acceptance**
- [ ] Φιλτράρισμα server-side: ο καλών παίρνει μόνο `recipient == self`, `sender == self` ή `All`
- [ ] Ο DM παίρνει τα πάντα
- [ ] Τα `is_secret` roll requests δεν διαρρέουν σε άλλους παίκτες
- [ ] Το client-side φίλτρο μένει ως άμυνα εις βάθος

---

### DM-04 · `POST /campaigns/join` can move another user's character
`security` `area:backend` `P0` · **S**

Το [`update_one({"char_id": char_id})`](server/routers/campaign_router.py#L143) δεν φιλτράρει
`owner_id`. Με ένα έγκυρο invite code μετακινείς **ξένο** χαρακτήρα σε καμπάνια.

**Acceptance**
- [ ] Το φίλτρο γίνεται `{"char_id": ..., "owner_id": current_user.id}`
- [ ] `404`/`403` αν ο χαρακτήρας δεν ανήκει στον καλούντα
- [ ] Test: χρήστης Β δεν μετακινεί χαρακτήρα του Α

---

# 🔴 P1 — Σπασμένη λειτουργικότητα

### DM-05 · Session Prep tab never shows a result
`bug` `area:frontend` `P1` · **XS** ⭐ *ξεκίνα από εδώ*

[dm.component.ts:781](client/src/app/features/dm/dm.component.ts#L781) διαβάζει
`res.prep_markdown`, το backend επιστρέφει `session_markdown`
([schemas.py:387](backend/core/schemas.py#L387)). Το `prepResult` μένει `undefined`.

**Acceptance**
- [ ] Διάβασμα του σωστού key → το tab εμφανίζει αποτέλεσμα
- [ ] Typed response interface αντί για `any`, ώστε να το πιάσει ο compiler την επόμενη φορά

---

### DM-06 · "Add Member" writes nothing to the server
`bug` `area:frontend` `area:backend` `P1` · **L**

Τα [`addExistingPartyMember()`](client/src/app/features/dm/dm.component.ts#L493) και
[`addPartyMember()`](client/src/app/features/dm/dm.component.ts#L533) γράφουν μόνο στο τοπικό
`campaignParties`. Στο επόμενο refresh ο ήρωας εξαφανίζεται. **2 από τα 3 tabs του modal
είναι διακοσμητικά** — μόνο το invite-code path δουλεύει.

**Acceptance**
- [ ] Endpoint που θέτει `active_campaign` σε χαρακτήρα (με owner check)
- [ ] Απόφαση για το "Custom Hero": ή δημιουργεί πραγματικό NPC record, ή **αφαιρείται το tab**
- [ ] Μετά από refresh το party παραμένει σωστό
- [ ] Σφάλμα API → ορατό error, όχι σιωπηλή τοπική επιτυχία

---

### DM-07 · Party HP and conditions are never persisted
`bug` `area:frontend` `area:backend` `P1` · **L**

`adjustHp()` και `toggleCondition()` μεταλλάσσουν μόνο τη μνήμη. Ο παίκτης δεν βλέπει
τίποτα, η βάση δεν μαθαίνει τίποτα, και το `conditions: []` είναι hardcoded στο load
([:459](client/src/app/features/dm/dm.component.ts#L459)). Για «Live Party Tracker» αυτό
είναι το κύριο feature.

**Acceptance**
- [ ] HP change → persist (debounced) + broadcast στον παίκτη μέσω WebSocket
- [ ] Conditions αποθηκεύονται στον χαρακτήρα και φορτώνονται
- [ ] Ο παίκτης βλέπει τη μεταβολή live, χωρίς refresh
- [ ] Οι ταυτόχρονες αλλαγές DM/παίκτη δεν πατάνε η μία την άλλη

---

### DM-08 · `activeTurnIndex` is never clamped
`bug` `area:frontend` `P1` · **S**

Ο δείκτης «Current» δείχνει λάθος πλάσμα μετά από `removeCombatant()` (splice χωρίς
προσαρμογή), `sortCombatants()` (ανακάτεμα μετά το roll all) ή campaign switch.
Το πιο ορατό bug στο τραπέζι.

**Acceptance**
- [ ] Το «Current» παραμένει στο **ίδιο πλάσμα** μετά από sort (κράτα `id`, όχι index)
- [ ] Αφαίρεση combatant πριν τον τρέχοντα δεν μετακινεί τη σειρά
- [ ] Αφαίρεση του τρέχοντα → πάει στον επόμενο
- [ ] Άδεια λίστα → καθαρή κατάσταση, όχι δείκτης εκτός ορίων

---

### DM-09 · Remove fake demo data and show real error states
`tech-debt` `area:frontend` `P1` · **M**

Το `campaignParties` έχει hardcoded Valeros/Ezren/Merisiel + 3 ψεύτικες καμπάνιες
([:145-161](client/src/app/features/dm/dm.component.ts#L145)). Σε **οποιοδήποτε** σφάλμα (π.χ.
ληγμένο token) ο DM βλέπει φαντάσματα χωρίς να το ξέρει. Ίδιο και το `createNewCampaign()`
που «δημιουργεί τοπικά» καμπάνια που δεν υπάρχει.

**Acceptance**
- [ ] Διαγραφή όλων των hardcoded rosters/campaigns
- [ ] Σφάλμα → ορατό error state με retry (`forge-empty-state`)
- [ ] `401` → redirect σε login, όχι demo data
- [ ] Το `createNewCampaign()` δεν «πετυχαίνει» ποτέ τοπικά όταν αποτυγχάνει το API

---

# 🟡 P2 — Σημαντικά αλλά όχι επείγοντα

### DM-10 · `copyInviteCode()` copies a hardcoded fake code
`bug` `area:frontend` `P2` · **XS**

[:527](client/src/app/features/dm/dm.component.ts#L527) — `this.inviteCode || '4D0705'`.
Χωρίς κωδικό, ο DM στέλνει στους παίκτες string που δεν ανοίγει τίποτα.

**Acceptance**
- [ ] Χωρίς κωδικό → πρόταση δημιουργίας, ποτέ fallback string
- [ ] Το κουμπί είναι disabled ή δημιουργεί κωδικό πρώτα

---

### DM-11 · `is_secret` announces the secret instead of hiding it
`bug` `area:frontend` `area:backend` `P2` · **M**

Ο παίκτης παίρνει toast `🔒 SECRET ROLL REQUESTED` **μαζί με το αποτέλεσμα**. Το flag
ανακοινώνει ότι κάτι κρύβεται, χωρίς να κρύβει τίποτα.

**Acceptance**
- [ ] Απόφαση σημασιολογίας: ή ρίχνει ο DM, ή ρίχνει ο παίκτης χωρίς να βλέπει το νούμερο
- [ ] Ο DM βλέπει πάντα το αποτέλεσμα
- [ ] Το secret request δεν εμφανίζεται στο ιστορικό άλλων παικτών (δες DM-03)

---

### DM-12 · Inconsistent `encodeURIComponent` on campaign names
`bug` `area:frontend` `P2` · **XS**

`whisper` και `roll-request` το κάνουν· `/party` ([:448](client/src/app/features/dm/dm.component.ts#L448)),
`/notes` ([:592](client/src/app/features/dm/dm.component.ts#L592)) και `/invite-code`
([:601](client/src/app/features/dm/dm.component.ts#L601)) όχι. Καμπάνια με `/` ή `#` σπάει.

**Acceptance**
- [ ] Όλα τα campaign names encoded — ιδανικά μέσω ενός helper
- [ ] Χειροκίνητος έλεγχος με όνομα που περιέχει `/` και `#`

---

### DM-13 · Initiative tracker has no rounds and no persistence
`feature` `area:frontend` `P2` · **L**

Λείπουν round counter, «Previous Turn», reset/end combat, διάρκεια conditions, death saves,
concentration. Και όλο το encounter ζει **μόνο στη μνήμη** — refresh και χάθηκε.

**Acceptance**
- [ ] Round counter, αυξάνεται στην αναδίπλωση της σειράς
- [ ] Previous Turn + End Combat (με επιβεβαίωση)
- [ ] Το encounter επιβιώνει refresh
- [ ] Εξαρτάται από **DM-08**

---

### DM-14 · Players never see whose turn it is
`feature` `area:frontend` `area:backend` `P2` · **M**

Το κανάλι υπάρχει ήδη — το `party_update` δηλώνεται στο
[`WsMessage`](client/src/app/core/services/websocket.service.ts) και **δεν στέλνεται ποτέ**.

**Acceptance**
- [ ] Ο DM αλλάζει σειρά → broadcast στους παίκτες
- [ ] Ο παίκτης βλέπει «Σειρά σου» ξεκάθαρα
- [ ] Εξαρτάται από **DM-13**

---

### DM-15 · Player has no agency over how they roll
`feature` `area:frontend` `P2` · **M**

Ο client auto-rollάρει με το που φτάσει το request (`// auto-rolling is faster`). Χάνονται
advantage/disadvantage, inspiration, bonus — δηλαδή το μισό D&D.

**Acceptance**
- [ ] Prompt αντί για auto-roll, με επιλογή advantage/disadvantage/normal
- [ ] Ο DM βλέπει τι mode χρησιμοποιήθηκε
- [ ] Timeout ή «missed» κατάσταση αν ο παίκτης δεν απαντήσει

---

### DM-16 · No way to delete a campaign or remove a member
`feature` `area:frontend` `area:backend` `P2` · **M**

Δεν υπάρχει `DELETE` campaign, «kick member» ή «leave campaign». Ο DM μόνο προσθέτει.

**Acceptance**
- [ ] `DELETE /campaigns/{name}` (μόνο owner, με επιβεβαίωση)
- [ ] Kick member → καθαρίζει το `active_campaign` του χαρακτήρα
- [ ] Leave campaign από τον παίκτη

---

### DM-17 · Whispers and roll requests grow unbounded in one Mongo document
`tech-debt` `area:backend` `P2` · **L**

Όριο 16MB ανά document, και κάθε whisper κάνει read-modify-write ολόκληρου του array →
**race condition** αν δύο στέλνουν ταυτόχρονα.

**Acceptance**
- [ ] Ξεχωριστά collections με index στο `campaign_name`
- [ ] Pagination στο `/messages`
- [ ] Migration script για τα υπάρχοντα δεδομένα
- [ ] Ταυτόχρονα whispers δεν χάνονται

---

### DM-18 · `generateEncounter()` ignores the actual party
`bug` `area:frontend` `P2` · **S**

Στέλνει σταθερά `party_size: 4` και `difficulty: 'Medium'`, ενώ ξέρει `partyMembers.length`
και `partyAverageLevel` — και το backend δέχεται και τα δύο. Το `avgLevel` είναι χειροκίνητο
πεδίο που ξεκινά στο 5 και δεν συγχρονίζεται ποτέ.

**Acceptance**
- [ ] Στέλνει πραγματικό `party_size` και `avg_level`
- [ ] Επιλογέας difficulty στο UI
- [ ] Το `avgLevel` προσυμπληρώνεται από το party, με δυνατότητα override

---

# 🔵 P3 — Μικρά / εκκρεμείς αποφάσεις

### DM-19 · Small DM workspace cleanups
`tech-debt` `area:frontend` `P3` · **S**

Ομαδοποιημένα one-liners:
- [ ] `PartyMember` / `InitiativeCombatant` → `core/models/` (τα κάνουν import 4 αρχεία)
- [ ] `wsService.disconnect()` στο `ngOnDestroy` του DmComponent
- [ ] `sendWhisper()` trim + validate (το inbox reply το κάνει ήδη σωστά)
- [ ] `passive_perception: 10 + Math.floor(((12) - 10) / 2)` → σκέτο `11` ή πραγματικός υπολογισμός

---

### DM-20 · Hardcoded `'2014 Edition'` in three places
`tech-debt` `area:frontend` `P3` · **S**

Το campaign doc έχει ήδη `dnd_edition` και το app έχει edition mode στο
`character-state.service`.

**Acceptance**
- [ ] Η edition διαβάζεται από campaign/app state σε όλα τα σημεία
- [ ] Καμία string literal edition στο `dm.component.ts`

---

### DM-21 · Decide the fate of `/dm/riddle`
`tech-debt` `area:backend` `P3` · **XS**

Το endpoint υπάρχει πλήρες στο backend και **μηδέν** references σε όλο το client.

**Acceptance**
- [ ] Απόφαση: ή μπαίνει στο Generators panel, ή αφαιρείται endpoint + service + schema

---

### DM-22 · No presence indicator for connected players
`feature` `area:frontend` `area:backend` `P3` · **M**

Ο DM στέλνει roll request χωρίς να ξέρει αν ο παίκτης είναι online. Ο `ConnectionManager`
ξέρει ήδη ποιος είναι συνδεδεμένος.

---

# Προτεινόμενο πρώτο sprint

| Σειρά | Ticket | Γιατί |
|---|---|---|
| 1 | **DM-05** | XS, ξεκλειδώνει ολόκληρο tab — γρήγορη νίκη |
| 2 | **DM-10**, **DM-12** | XS, καθαρίζουν αμηχανίες |
| 3 | **DM-08** | Το πιο ορατό bug στο τραπέζι |
| 4 | **DM-02**, **DM-04** | Τα δύο μικρότερα security — ξεκινάει η δουλειά authz |
| 5 | **DM-09** | Καθαρίζει τα demo φαντάσματα πριν χτιστεί τίποτα από πάνω |

Τα **DM-06** και **DM-07** είναι τα πιο πολύτιμα αλλά θέλουν backend — άρα άρση του
περιορισμού στο `client/CLAUDE.md` ή ξεχωριστό backend πέρασμα.
