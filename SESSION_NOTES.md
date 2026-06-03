# 📜 Session Notes — Phyrexian Forge (2026-06-04)

Αυτό το αρχείο περιγράφει τι υλοποιήθηκε, τι προβλήματα υπάρχουν, και τι απομένει να γίνει.

---

## ✅ Τι υλοποιήθηκε σε αυτή τη συνεδρία

### 1. Owner ID στο Party Dashboard (DM Workspace)
**Αρχείο:** `views/dm_workspace.py` → `_render_party_dashboard()` (~line 2040)

Κάτω από το όνομα και την κλάση κάθε χαρακτήρα εμφανίζεται πλέον:
```
👤 Owner: `<owner_id>`
```
Το `owner_id` προέρχεται από το `member.get('owner_id', 'Unknown')`.

---

### 2. Roll Requests: εμφάνιση μόνο του τελευταίου
**Αρχείο:** `views/player_dashboard.py` → `render_dm_roll_notifications()` (~line 800)

**Πριν:** Ο κώδικας κάνε loop σε όλες τις καμπάνιες και εμφάνιζε **όλα** τα ενεργά roll requests (pending ή completed) για τον χαρακτήρα.

**Μετά:** Συγκεντρώνει όλα τα requests από όλες τις καμπάνιες, τα ταξινομεί με βάση `created_at`, και εμφανίζει **μόνο το τελευταίο**.

**Σημαντική λεπτομέρεια:** Κατά τη διόρθωση δημιουργήθηκε `IndentationError` λόγω λανθασμένης στοίχισης. Διορθώθηκε με regex replace script. Η `pre-commit` (ruff + pytest) περνά ✅.

---

### 3. Whisper Chat (DM ↔ Player)
**Αρχεία:**
- `backend/core/storage.py` → `send_whisper()` (~line 351)
- `views/dm_workspace.py` → `render_dm_whisper_chat_fragment()` (~line 2099)
- `views/player_dashboard.py` → `render_dm_whispers_channel()` (~line 974)

**Backend (`send_whisper`):**
- Αποθηκεύει whispers με `sender`, `recipient`, `message`, `timestamp`
- Channel partitioning: αν `recipient == "All"` → channel `"All"`, αλλιώς → channel = το όνομα του χαρακτήρα (player side)
- Κρατά **μόνο τα τελευταία 3** ανά channel στη βάση δεδομένων

**DM Side (`dm_workspace.py`):**
- Fragment με auto-refresh κάθε 5 δευτερόλεπτα
- Dropdown επιλογής παραλήπτη (κάθε party member + "All (Broadcast)")
- `st.form(clear_on_submit=True)` για αυτόματο καθαρισμό input
- Φιλτράρει whispers: DM→Player ή Player→DM για τον επιλεγμένο παραλήπτη
- Εμφανίζει τελευταία 3

**Player Side (`player_dashboard.py`):**
- Fragment με auto-refresh κάθε 5 δευτερόλεπτα
- Collapsible expander "💬 DM Whisper Channel"
- Φιλτράρει: `sender == char_name` ή `recipient == char_name` ή `recipient == "All"`
- `st.form(clear_on_submit=True)` για αυτόματο καθαρισμό
- Εμφανίζει τελευταία 3

---

### 4. Fixes StreamlitAPIException
**Πρόβλημα:** Κώδικας έκανε `st.session_state["dm_whisper_text_input"] = ""` μετά τη δημιουργία του widget → `StreamlitAPIException`.

**Λύση:** Και στο DM και στο Player side αντικαταστάθηκε με `st.form(key=..., clear_on_submit=True)`.

---

## ⚠️ Γνωστά προβλήματα / Αδοκίμαστα

### 🔴 Whisper end-to-end: δεν έγινε live browser test
Ο browser subagent τερμάτισε (429 rate limit) πριν ολοκληρώσει τον έλεγχο. Δεν επαληθεύτηκε οπτικά αν:
- Το DM στέλνει μήνυμα σε player και το βλέπει ο player
- Ο player απαντά και το βλέπει ο DM

### 🟡 Πιθανό πρόβλημα: Whisper recipient matching
**Ρίσκο:** Το DM επιλέγει recipient από dropdown βάσει `char_name` (π.χ. "Echo of the Chime"). Το `send_whisper` αποθηκεύει `recipient = "Echo of the Chime"`.

Στο player side, το φίλτρο ελέγχει `w.get("recipient") == char_name`. Αυτό δουλεύει **μόνο αν** το `char_name` στο `st.session_state` ταιριάζει ακριβώς με αυτό που επέλεξε ο DM.

**Πώς να το ελέγξεις:** Ο DM επιλέγει player από την καμπάνια. Αυτοί οι names προέρχονται από:
```python
# dm_workspace.py ~line 2083
recipients = ["All (Broadcast)"] + [
    camp_data["party_member_data"][fn].get("char_name", fn)
    for fn in camp_data.get("party", [])
]
```
Αν το `char_name` που εμφανίζεται εκεί **δεν ταιριάζει** με το `st.session_state.get("char_name")` στο Player Dashboard, τα whispers δεν θα φαίνονται.

### 🟡 Whisper: δεν υπάρχει notification για νέο μήνυμα
Ο player δεν ειδοποιείται αν λάβει νέο whisper εκτός αν έχει ανοιχτό το expander. Το fragment κάνει refresh κάθε 5s αλλά χωρίς visual indication.

---

## 📁 Βασικά αρχεία που αφορούν αυτές τις λειτουργίες

| Αρχείο | Σκοπός |
|--------|--------|
| `backend/core/storage.py` | `send_whisper()`, `clear_whispers()`, `add_roll_request()`, `submit_roll_result()` |
| `backend/repositories/campaign_repository.py` | `save()` / `load()` — πεδία `whispers`, `roll_requests` |
| `views/dm_workspace.py` | DM Workspace: Whisper Chat tab, Party Dashboard, Roll requests |
| `views/player_dashboard.py` | Player Dashboard: roll notifications fragment, whisper channel fragment |
| `backend/core/schemas.py` | `WhisperSchema` (validation) |
| `tests/test_storage_facade.py` | Unit tests για whispers, roll requests, pruning |

---

## 🔧 Τι πρέπει να γίνει αν υπάρχει πρόβλημα με τα whispers

1. **Έλεγξε το channel key στο `send_whisper`:**
   ```python
   channel_key = r if s == "DM" else s
   ```
   Αν ο DM στέλνει σε "Echo of the Chime", το `channel_key = "Echo of the Chime"`.
   Αν ο player στέλνει, `sender = "Echo of the Chime"`, `channel_key = "Echo of the Chime"`.

2. **Έλεγξε τι επιστρέφει το dropdown στο DM Workspace:**
   Αναζήτα γύρω από line 2083 του `dm_workspace.py` πώς φτιάχνεται η λίστα `recipients`.

3. **Έλεγξε τo `char_name` στο session_state του player:**
   Στο `player_dashboard.py`, το `char_name = st.session_state.get("char_name", "")`. Αυτό πρέπει να ταιριάζει **ακριβώς** με αυτό που βλέπει ο DM.

4. **Δοκίμασε με MongoDB query:**
   ```js
   db.campaigns.findOne({campaign_name: "mitsos"}).whispers
   ```
   Αυτό δείχνει αν τα whispers αποθηκεύονται σωστά.

---

## 🧪 Τελευταία κατάσταση tests
```
pre-commit: ✅ All passed (ruff + pytest 149 tests)
```
