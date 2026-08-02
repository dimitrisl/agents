# Ανάλυση DM Workspace (Front + Back)

> Ανάλυση μόνο — καμία αλλαγή κώδικα δεν έγινε.
> Ημερομηνία: 2026-08-03 · Branch: `testing_grounds`

---

## Τι κάνει σήμερα

**Front** — Το [dm.component.ts](client/src/app/features/dm/dm.component.ts) είναι ένας «θεός-controller» (815 γραμμές) που κρατάει όλο το state, με καθαρά presentational παιδιά (5 panels, 5 modals, header, inbox). Έχει:

- επιλογή / δημιουργία campaign, invite code
- campaign notes
- party tracker (HP / conditions / quick ability checks)
- initiative tracker
- AI generators (encounter / NPC)
- session prep
- whispers + roll requests μέσω WebSocket, με catch-up σε κάθε reconnect

**Back**

- [campaign_router.py](server/routers/campaign_router.py) — CRUD + whispers + roll requests σε Mongo
- [dm_router.py](server/routers/dm_router.py) — 4 AI endpoints (encounter, npc, riddle, session-prep)
- [websocket_router.py](server/routers/websocket_router.py) — server-authored κανάλι με targeted delivery ανά χαρακτήρα (**αυτό είναι σωστά φτιαγμένο**)

---

## 🔴 Πραγματικά bugs

### 1. Το Session Prep δεν εμφανίζει ποτέ αποτέλεσμα

[dm.component.ts:781](client/src/app/features/dm/dm.component.ts#L781) διαβάζει `res.prep_markdown`, αλλά το backend επιστρέφει `session_markdown` ([schemas.py:387](backend/core/schemas.py#L387)).

Το `prepResult` μένει `undefined` → το `*ngIf="prepResult"` δεν ανοίγει ποτέ. **Ολόκληρο tab νεκρό.**

### 2. «Add Member» είναι ψεύτικο UI

Και το [`addExistingPartyMember()`](client/src/app/features/dm/dm.component.ts#L493) και το [`addPartyMember()`](client/src/app/features/dm/dm.component.ts#L533) γράφουν **μόνο** στο τοπικό `campaignParties`. Καμία κλήση API, το `active_campaign` του χαρακτήρα δεν τίθεται ποτέ.

Στο επόμενο refresh / campaign switch το `onCampaignSelect()` ξαναφορτώνει από `/party` και ο ήρωας εξαφανίζεται. Μόνο το invite-code path δουλεύει στ' αλήθεια.

> Αυτό είναι το χειρότερο εύρημα — 2 από τα 3 tabs του modal είναι διακοσμητικά.

### 3. HP και conditions του party δεν αποθηκεύονται πουθενά

`adjustHp()` και `toggleCondition()` μεταλλάσσουν το object στη μνήμη. Ο παίκτης δεν βλέπει τίποτα, η βάση δεν μαθαίνει τίποτα, και το `conditions: []` είναι hardcoded στο load ([:459](client/src/app/features/dm/dm.component.ts#L459)).

Για ένα «Live Party Tracker» αυτό είναι κενό, όχι λεπτομέρεια. Το ίδιο ισχύει και για το `ngModel` στο HP input του party panel.

### 4. `activeTurnIndex` δεν κλειδώνεται ποτέ

- `removeCombatant()` κάνει splice χωρίς προσαρμογή του δείκτη
- `sortCombatants()` ανακατεύει τη λίστα μετά το `rollAllInitiative()`
- `importPartyToInitiative(true)` πετάει τους players

Σε κάθε περίπτωση ο δείκτης «Current» δείχνει ξαφνικά άλλο πλάσμα ή έξω από τον πίνακα. Σε initiative tracker αυτό είναι το πιο ορατό bug στο τραπέζι.

### 5. `copyInviteCode()` αντιγράφει ψεύτικο κωδικό

[:527](client/src/app/features/dm/dm.component.ts#L527) — `this.inviteCode || '4D0705'`.

Αν δεν υπάρχει κωδικός, ο DM στέλνει στους παίκτες ένα hardcoded string που δεν ανοίγει τίποτα.

### 6. Το `is_secret` λειτουργεί ανάποδα

Ο server το broadcast-άρει κανονικά στον παίκτη, ο player client auto-rollάρει και δείχνει toast `🔒 SECRET ROLL REQUESTED` **μαζί με το αποτέλεσμα** στο inbox του.

Δηλαδή το flag *ανακοινώνει* στον παίκτη ότι κάτι κρύβεται, χωρίς να κρύβει τίποτα. Για D&D, secret roll σημαίνει ότι ρίχνει ο DM, ή τουλάχιστον ότι ο παίκτης δεν βλέπει το νούμερο.

---

## 🔒 Backend — διαρροές και έλεγχοι που λείπουν

Το `campaign_name` χρησιμοποιείται ως primary key, χωρίς `campaign_id` και **χωρίς κανέναν έλεγχο ιδιοκτησίας**.

| Πρόβλημα | Πού | Συνέπεια |
|---|---|---|
| `GET /campaigns/` επιστρέφει τα DM notes στους παίκτες | Το `CampaignSchema` περιλαμβάνει `notes`, `whispers`, `roll_requests` και κάθε μέλος του party παίρνει ολόκληρο το doc | Τα μυστικά plot hooks του DM είναι ένα devtools tab μακριά |
| `GET /{name}/messages` δίνει σε κάθε authenticated χρήστη **όλα** τα whispers | Φιλτράρισμα μόνο client-side ([player.component.ts:779](client/src/app/features/player/player.component.ts#L779)) | Ο παίκτης A διαβάζει τα ιδιωτικά whispers του DM προς τον παίκτη B με ένα `curl` |
| `POST /campaigns/` κάνει upsert **by name** | [campaign_router.py:89](server/routers/campaign_router.py#L89) | Όποιος φτιάξει campaign με ίδιο όνομα σβήνει notes/party ξένης καμπάνιας |
| Κανένα endpoint δεν ελέγχει `owner_id` | `/{name}/notes`, `/{name}/roll-request`, `/{name}/whisper` | Οποιοσδήποτε γράφει σε οποιαδήποτε καμπάνια |
| `POST /campaigns/join` κάνει `update_one({"char_id": char_id})` **χωρίς** `owner_id` φίλτρο | [campaign_router.py:143](server/routers/campaign_router.py#L143) | Με ένα έγκυρο invite code μετακινείς **ξένο** χαρακτήρα σε καμπάνια |

> Το WebSocket routing είναι προσεκτικά φτιαγμένο ακριβώς για την ιδιωτικότητα των whispers — και το REST layer το ακυρώνει εντελώς.

### Μοντέλο δεδομένων

Τα `roll_requests` και `whispers` μεγαλώνουν άπειρα μέσα σε **ένα** έγγραφο Mongo:

- όριο 16MB ανά document
- κάθε whisper κάνει read-modify-write ολόκληρου του array → **race condition** αν δύο στέλνουν ταυτόχρονα

Χρειάζονται δικά τους collections με index στο `campaign_name`.

---

## ⚠️ Λείπουν (για εργαλείο D&D)

- **Καμία διαγραφή** — δεν υπάρχει `DELETE` campaign, ούτε «kick / remove member», ούτε «leave campaign». Ο DM μόνο προσθέτει.
- **Initiative tracker χωρίς γύρους** — κανένας round counter, κανένα «Previous Turn», κανένα reset / end combat, καμία διάρκεια για conditions, κανένα death save, κανένα concentration tracking.
- **Το combat είναι μόνο στη μνήμη** — refresh και χάθηκε ολόκληρο το encounter.
- **Το initiative δεν φτάνει στους παίκτες** — το κανάλι υπάρχει (`party_update` δηλώνεται ήδη στο [`WsMessage`](client/src/app/core/services/websocket.service.ts) και δεν στέλνεται ποτέ), αλλά ο παίκτης δεν ξέρει πότε είναι η σειρά του.
- **Καμία ένδειξη ποιος παίκτης είναι online** — ο DM στέλνει roll request στο κενό.
- **Το `/dm/riddle` υπάρχει στο backend και δεν το καλεί κανείς** — μηδέν references σε όλο το client.
- **Ο παίκτης δεν επιλέγει ποτέ πώς ρίχνει** — ο client auto-rollάρει με το που φτάσει το request (`// auto-rolling is faster`). Χάνεται advantage / disadvantage, inspiration, bonus — δηλαδή το μισό D&D.

---

## 🤨 Παράξενα / ανούσια

### Fake demo data ως fallback παραγωγής

Το `campaignParties` έχει hardcoded Valeros / Ezren / Merisiel, Curse of Strahd, Phyrexia Awakens ([:145-161](client/src/app/features/dm/dm.component.ts#L145)), και το `loadCampaigns()` σε **οποιοδήποτε** σφάλμα (π.χ. ληγμένο token) γεμίζει το dropdown με 3 ψεύτικες καμπάνιες με ψεύτικα invite codes.

Ο DM δεν έχει τρόπο να καταλάβει ότι κοιτάει φαντάσματα. Το ίδιο και στο `createNewCampaign()` που «δημιουργεί τοπικά» μια καμπάνια που δεν υπάρχει πουθενά.

### Ασυνεπές URL encoding

`whisper` και `roll-request` χρησιμοποιούν `encodeURIComponent`, ενώ **δεν** το κάνουν:

- `/party` — [:448](client/src/app/features/dm/dm.component.ts#L448)
- `/notes` — [:592](client/src/app/features/dm/dm.component.ts#L592)
- `/invite-code` — [:601](client/src/app/features/dm/dm.component.ts#L601)

Καμπάνια με `/` ή `#` στο όνομα σπάει τα μισά endpoints.

### Λοιπά

- **`'2014 Edition'` hardcoded σε 3 σημεία**, ενώ το campaign doc έχει ήδη `dnd_edition` και το app έχει edition mode στο `character-state.service`.
- **Το `generateEncounter()` αγνοεί το party** — στέλνει `party_size: 4` και `difficulty: 'Medium'` σταθερά, ενώ ξέρει `partyMembers.length` και `partyAverageLevel`, και το backend δέχεται και τα δύο. Το `avgLevel` είναι ξεχωριστό χειροκίνητο πεδίο που ξεκινά στο 5 και δεν συγχρονίζεται ποτέ με το πραγματικό.
- **`addPartyMember()` γράφει** `passive_perception: 10 + Math.floor(((12) - 10) / 2)` — δηλαδή `11`, γραμμένο ως πράξη με literal για να μοιάζει υπολογισμός.
- **Τα `PartyMember` / `InitiativeCombatant` interfaces ζουν μέσα στο component** και τα κάνουν import 4 άλλα αρχεία — ανήκουν στο `core/models`.
- **Ο DM δεν κάνει `wsService.disconnect()` στο `ngOnDestroy`** — φεύγοντας από τη σελίδα το socket μένει ανοιχτό ως `role=dm`.
- **`sendWhisper()` δεν κάνει trim / validate** — ο DM μπορεί να στείλει κενό whisper. (Το inbox reply το ελέγχει σωστά, το modal όχι.)

---

## Προτεινόμενη σειρά προτεραιότητας

| # | Ενέργεια | Πλευρά | Μέγεθος |
|---|---|---|---|
| 1 | Διόρθωση `prep_markdown` → `session_markdown` | Front | 1 γραμμή — ξεκλειδώνει ολόκληρο tab |
| 2 | Clamping του `activeTurnIndex` | Front | Μικρό, ορατό σε κάθε session |
| 3 | Persist party membership + HP / conditions | Front **+ Back** | Χωρίς αυτό το party tab είναι ψεύτικο |
| 4 | Authorization + φιλτράρισμα whispers server-side | Back | Τα DM notes και τα ιδιωτικά whispers είναι εκτεθειμένα σήμερα |
| 5 | Αφαίρεση demo fallbacks, εμφάνιση πραγματικού error state | Front | Μεσαίο |

> ⚠️ Το `client/CLAUDE.md` ορίζει ότι δουλεύουμε **μόνο** front-end. Τα #3 και #4 χρειάζονται ξεχωριστό πέρασμα ή άρση του περιορισμού.
