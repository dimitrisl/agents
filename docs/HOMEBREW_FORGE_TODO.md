# Backend TODO — Homebrew AI Forge

Αυτό το έγγραφο λειτουργεί ως το κεντρικό ticket/board για την υλοποίηση του **AI Homebrew Forge**. Σκοπός είναι να επιτρέψουμε στον Dungeon Master (DM) να δημιουργεί custom αντικείμενα (Items, Weapons), Skills, και NPCs με τη βοήθεια του AI, διατηρώντας αυστηρά τον έλεγχο πρόσβασης.

---

## 1. Role-Based Access & Campaign Scoping (Κρίσιμο)
Το σύστημα πρέπει να είναι απολύτως στεγανό.
- [ ] **DM Authorization:** Μόνο ο χρήστης που έχει το ρόλο του DM για ένα συγκεκριμένο `campaign_id` έχει δικαίωμα να κάνει POST/PUT/DELETE στο `/homebrew` endpoint. (Απαιτείται FastAPI Dependency π.χ. `verify_dm_access`).
- [ ] **Campaign Scoping:** Κάθε homebrew στοιχείο αποθηκεύεται με ένα υποχρεωτικό πεδίο `campaign_id`. Όταν ένας παίκτης αναζητά όπλα ή ξόρκια, το query πρέπει να φέρνει τα στατικά JSONs **συν** τα homebrew έγγραφα όπου `homebrew.campaign_id == player.current_campaign_id`. Οι παίκτες σε άλλα campaigns δεν πρέπει ποτέ να βλέπουν αυτά τα αντικείμενα.

## 2. Export / Import System (DM Sharing)
Οι DMs πρέπει να μπορούν να μοιράζονται τις δημιουργίες τους μεταξύ τους.
- [ ] **Export Endpoint (`GET /homebrew/export?campaign_id=...`)**: Θα παράγει ένα Base64 encoded string ή ένα καθαρό JSON αρχείο που θα περιέχει όλα τα Homebrew αντικείμενα/NPCs του campaign.
- [ ] **Import Endpoint (`POST /homebrew/import`)**: Ένας άλλος DM θα μπορεί να ανεβάζει το JSON (ή να κάνει paste το token) και το backend θα διαβάζει τα αντικείμενα, θα αλλάζει το `campaign_id` στο δικό του campaign, και θα τα κάνει insert στη βάση του.

## 3. Database & Schemas (MongoDB)
Τα custom αντικείμενα πρέπει να είναι απόλυτα συμβατά με τα official Pydantic models.
- [ ] Δημιουργία collection `homebrew_content` στη MongoDB.
- [ ] Σχήματα Pydantic: `HomebrewItemSchema`, `HomebrewFeatureSchema`, `HomebrewNPCSchema`. Όλα θα κληρονομούν τα base properties από τα official schemas, αλλά θα προσθέτουν τα: `creator_dm_id` και `campaign_id`.

## 4. The AI "Forge" Engine (`homebrew_service.py`)
Ο DM δεν χρειάζεται να γνωρίζει JSON. Θα τα γράφει σε φυσική γλώσσα.
- [ ] **Endpoint `POST /homebrew/forge`:**
  - Παίρνει ένα prompt: π.χ. "Θέλω ένα cursed σπαθί που ρουφάει 1d6 ζωή και την δίνει σε μένα, αλλά αν φέρω 1 στο ζάρι παθαίνω poison".
  - Καλεί το `LLMProvider.generate_json()` περνώντας το αυστηρό `HomebrewItemSchema` στο AI.
  - Το AI επιστρέφει το structure (e.g. `damage_dice="1d8", damage_type="slashing", properties=["Cursed", "Lifesteal"]`).
- [ ] **Validation Layer:** Το παραγόμενο JSON επικυρώνεται (Pydantic validation) πριν γίνει save στη MongoDB, για να αποφευχθεί διαφθορά δεδομένων (data corruption) κατά τη μάχη.

## 5. Integration με το `RulesRepository`
- [ ] Δημιουργία του `CampaignRulesFacade` ή τροποποίηση του `RulesRepository`. Οι μέθοδοι όπως `get_all_weapons()` πλέον θα δέχονται ένα optional `campaign_id`. Αν υπάρχει, θα κάνουν merge τα local JSONs με το Mongo collection.
- [ ] Το `stats_service.py` δεν θα χρειαστεί καμία αλλαγή αν το schema είναι ίδιο!

---

## 🚀 Επόμενα Βήματα (Execution Order)
1. Στήσιμο των **Pydantic Schemas** (βάσει του `core/schemas.py`).
2. Δημιουργία του **MongoDB Collection** και του CRUD service.
3. Υλοποίηση του **Auth Guard** (`verify_dm_access`).
4. Σύνδεση με το **LLMProvider** για το AI Generation.
5. Στήσιμο του **Export/Import** logic.

## 6. Frontend UI / UX (Angular)
Ο DM χρειάζεται ένα εύχρηστο γραφικό περιβάλλον για να αλληλεπιδρά με το σύστημα.
- [ ] **Homebrew Management Dashboard:** Ένα tab στο DM Workspace (ή ένα κεντρικό Modal) όπου θα φαίνονται όλα τα υπάρχοντα custom αντικείμενα του campaign.
- [ ] **AI Forge Popup/Modal:** Μία ειδική φόρμα (dialog/modal) που θα ανοίγει όταν ο DM πατάει "Create Homebrew".
  - Θα περιέχει ένα text area για το φυσικό κείμενο / prompt (π.χ. "Φτιάξε ένα σπαθί φωτιάς").
  - Θα δείχνει ένα loading/forging animation κατά την κλήση στο backend.
  - Θα επιστρέφει το αποτέλεσμα (τα stats του αντικειμένου) σε preview mode, επιτρέποντας στον DM να κάνει manual edits πριν το αποθηκεύσει τελικά στη βάση.
- [ ] **Import/Export UI:** Κουμπιά μέσα στο dashboard για το Import (paste JSON / file upload) και Export (download JSON / copy to clipboard).
