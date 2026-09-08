# 🛠️ Frontend UI Tasks & Handoff for @michalis89

Αυτό το έγγραφο περιέχει όλες τις αλλαγές που έγιναν στο Backend και απαιτούν αντίστοιχες ενέργειες στο Angular Frontend (από τον Μιχάλη) για να κλείσουν οι "τρύπες" στο UI ή για να αξιοποιηθούν νέα features.

---

## 🚨 ΠΡΟΣΟΧΗ: Αλλαγές Ασφαλείας που ίσως "σπάσουν" το υπάρχον UI

Το backend πλέον ελέγχει αυστηρά τα δικαιώματα (Ownership & Roles).

### 1. WebSockets & Role Spoofing
- **Τι άλλαξε:** Το WebSocket endpoint αγνοεί το URL parameter `role`. Πλέον ρωτάει τη βάση δεδομένων. Αν ένας παίκτης συνδεθεί και το Angular στείλει `?role=dm`, το backend τον βάζει στο δωμάτιο ως **player**.
- **Η "Τρύπα":** Αν το Angular UI επιτρέπει σε έναν Player να βλέπει το DM Workspace και να πατάει κουμπιά (π.χ. Roll Request), τα REST endpoints θα του πετάνε `403 Forbidden` (και θα βγαίνει το μήνυμα *"Could not reach [Target]"*).
- **Action:** Σιγουρέψου ότι τα Guards στο Angular δεν επιτρέπουν σε παίκτες να μπαίνουν σε `/dm-workspace` routes.

### 2. Campaign Member Role
- **Τι άλλαξε:** Πλέον για να κάνει κάποιος DM actions (όπως το να στείλει Roll Request), πρέπει να υπάρχει εγγραφή στο `campaign_members` με ρόλο `dm`. Το backend φροντίζει να εισάγει τον δημιουργό της καμπάνιας αυτόματα.

---

## ✨ Νέα Features προς υλοποίηση στο UI

### 1. Διαγραφή Καμπάνιας & Αφαίρεση Παικτών (Issue #27)
- **Τι φτιάχτηκε:**
  - `DELETE /api/v1/campaigns/{name}`
  - `DELETE /api/v1/campaigns/{name}/party/{char_id}`
- **Action:** Πρόσθεσε κουμπί "Delete Campaign" στα Settings του DM Workspace. Επίσης, πρόσθεσε ένα κουμπί "Kick" ή "Remove" δίπλα από κάθε παίκτη στο Party Panel.
- **SOS:** Όταν αφαιρείται ένας παίκτης ή διαγράφεται η καμπάνια, το backend κάνει broadcast WebSocket event (`type: "party_update", action: "removed"` ή `type: "campaign_deleted"`). Το UI πρέπει να "ακούει" αυτά τα events και να διώχνει τον παίκτη στην αρχική οθόνη.

### 2. Live Presence Indicators (Online/Offline) (Issue #35)
- **Τι φτιάχτηκε:** Τα WebSockets στέλνουν πλέον:
  - Μήνυμα `presence_sync` μόλις μπεις, με το ποιοι είναι *ήδη* μέσα.
  - Μήνυμα `presence_update` (`status: "online"` ή `"offline"`) όταν μπαίνει ή βγαίνει κάποιος.
- **Action:** Βάλε ένα "πράσινο λαμπάκι" (🟢) δίπλα στα ονόματα των παικτών στο Party Panel όταν είναι online, και γκρι (⚪) όταν είναι offline.

### 3. Προσθήκη Μελών (Issue #17)
- **Τι φτιάχτηκε:** Το endpoint `POST /api/v1/campaigns/{name}/party/members` δουλεύει πλέον και δέχεται λίστα από `char_ids` για να βάλει NPCs ή άλλους δικούς του χαρακτήρες ο DM.
- **Action:** Συνέδεσε το Modal "Add Member" του UI με αυτό το endpoint.

### 4. Εμφάνιση Usernames δίπλα στο Party (Νέο)
- **Τι φτιάχτηκε:** Το endpoint του Party (`GET /{name}/party`) επιστρέφει πλέον και το πεδίο `owner_username` για κάθε χαρακτήρα.
- **Action:** Στο Party Panel του DM, κάνε render το όνομα του παίκτη σε παρένθεση: `{{ member.char_name }} ({{ member.owner_username }})`.

### 5. AI Riddle Generator (Issue #34)
- **Τι φτιάχτηκε:** Κρατήσαμε το endpoint `/api/v1/dm/riddle` μετά από εντολή του Product Owner.
- **Action:** Φτιάξε ένα UI στο Session Prep tab (ένα μικρό Section "Generate Puzzle/Riddle") το οποίο να χτυπάει το endpoint και να εμφανίζει το output.

---

## 🛠️ Tech Debt & Συνδέσεις Υπαρχόντων Features

### 1. Request Initiative
- Το backend υποστηρίζει ήδη roll request για initiative.
- Στο `roll-request-modal.component.html`, απλά βάλε `Initiative` στο dropdown. Αν στείλεις `roll_type: "initiative"`, το backend ξέρει τι να κάνει (πέφτει σε καθαρό `DEX` check).
- (Optional) Φτιάξε ένα κουμπί "Request Initiative for All" στο Initiative Panel.

### 2. Party HP and Conditions (Issue #18)
- **ΔΕΝ** χρειάζεται backend κώδικας για αυτό! Υπάρχει ήδη.
- **Action:** Στα methods `adjustHp` και `toggleCondition` του Angular, κάνε call το `PATCH /api/v1/campaigns/{name}/party/{char_id}/state` με payload `{ "hp_current": X, "conditions": [...] }`. Βάλε ένα `debounceTime` (rxjs) για να μη σπαμάρεις τη βάση με κάθε κλικ.

### 3. Προσοχή στα Char Filenames vs IDs (Tech Debt)
- Πολλά endpoints σήμερα βασίζονται στο filename (π.χ. `grog_strongjaw_123.json`). Αν αλλάξετε τον τρόπο που γράφονται τα filenames στο UI, θα σπάσουν τα string splits στο backend. Ιδανικά στο μέλλον, το Angular πρέπει να στέλνει σκέτα `char_id`!
