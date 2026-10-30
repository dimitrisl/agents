import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeIconComponent,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgePageComponent,
} from '../../shared/ui';

export interface FaqItem {
  id: string;
  category: 'dm' | 'player' | 'companion' | 'forge' | 'vtt' | 'rules' | 'admin';
  categoryLabel: string;
  badgeTone: 'accent' | 'success' | 'gold' | 'danger' | 'muted';
  question: string;
  answerHtml: string;
  tags: string[];
}

@Component({
  selector: 'app-faq',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeIconComponent,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgePageComponent,
  ],
  templateUrl: './faq.component.html',
  styleUrl: './faq.component.css',
})
export class FaqComponent {
  searchQuery = signal<string>('');
  selectedCategory = signal<string>('dm');
  openQuestions = signal<Set<string>>(
    // First question of each axis starts open; the rest are one click away.
    new Set([
      'dm-1',
      'player-1',
      'companion-1',
      'forge-1',
      'vtt-1',
      'rules-1',
      'admin-1',
    ])
  );

  readonly categories = [
    { id: 'dm', label: '🏰 Dungeon Master (DM)', icon: '🏰' },
    { id: 'player', label: '🗡️ Παίκτης (Player)', icon: '🗡️' },
    { id: 'companion', label: '📱 Mobile Companion', icon: '📱' },
    { id: 'forge', label: '✦ Character Forge & Imports', icon: '✦' },
    { id: 'vtt', label: '🗺️ VTT & Homebrew', icon: '🗺️' },
    { id: 'rules', label: '📚 Κανόνες & AI Arbiter', icon: '📚' },
    { id: 'admin', label: '🛡️ Admin & Ασφάλεια', icon: '🛡️' },
  ];

  readonly faqItems: FaqItem[] = [
    // ==========================================
    // 1. ΑΞΟΝΑΣ DUNGEON MASTER (DM CAPABILITIES)
    // ==========================================
    {
      id: 'dm-1',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Πώς οργανώνεται το DM Workspace, η διαχείριση Campaigns, τα Invite Codes και το Sticky Session Board;',
      answerHtml: `
        <p>Το <strong>DM Workspace (<code>/dm</code>)</strong> είναι το κέντρο διοίκησης του Dungeon Master (σχεδιασμένο για Desktop/Laptop οθόνες <code>&ge; 1024px</code>) και περιλαμβάνει:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🏰 Campaign Header &amp; Εναλλαγή Καμπάνιας:</strong> Γρήγορη επιλογή ενεργού campaign από dropdown, δημιουργία νέου campaign (με τίτλο, αρχικές σημειώσεις και επιλογή κανόνων <strong>2014 Edition</strong> ή <strong>2024 Revision</strong>) και διαγραφή campaign.</li>
          <li><strong>🔑 6-Ψήφιο Invite Code:</strong> Παραγωγή ή ανανέωση μοναδικού κωδικού πρόσκλησης με ένα κλικ, ώστε οι παίκτες να συνδέσουν τους χαρακτήρες τους στο τραπέζι μέσω <em>Join Campaign</em>.</li>
          <li><strong>📊 Sticky Session Board (Αριστερή Στήλη):</strong> Μόνιμο πάνελ ελέγχου που δείχνει σε πραγματικό χρόνο:
            <ul class="list-disc list-inside ml-5 mt-1 space-y-0.5 text-sm">
              <li>Μετρητές <strong>Party Size</strong>, <strong>Average Level</strong>, <strong>In Combat</strong> και <strong>Current Turn / Round</strong>.</li>
              <li><strong>Party Health Mini-Bars:</strong> Ζωντανές μπάρες υγείας (<code>hp_current / hp_max</code>) και πορτρέτα όλων των μελών του party.</li>
              <li><strong>🗺️ Open VTT Grid:</strong> Κουμπί που ανοίγει το 2D Virtual Tabletop ταυτόχρονα στην οθόνη του DM και σε όλους τους συνδεδεμένους παίκτες μέσω WebSocket (<code>vtt_toggle</code>).</li>
            </ul>
          </li>
        </ul>
      `,
      tags: ['dm', 'campaign', 'invite code', 'session board', 'vtt toggle', 'edition'],
    },
    {
      id: 'dm-2',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Τι προσφέρει το Live Party Tracker (👥 Party Tab) στον DM κατά τη διάρκεια του παιχνιδιού;',
      answerHtml: `
        <p>Η καρτέλα <strong>👥 Live Party Tracker</strong> δίνει στον DM πλήρη εικόνα και έλεγχο πάνω στους ήρωες της ομάδας:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🟢 Live WebSocket Presence:</strong> Ζωντανή ένδειξη <code>🟢 Online</code> ή <code>⚪ Offline</code> δίπλα στο όνομα και το username κάθε παίκτη.</li>
          <li><strong>❤️ Real-Time HP Steppers &amp; Direct Input:</strong> Αυξομείωση HP με κουμπιά <code>− / +</code> ή απευθείας πληκτρολόγηση αριθμού. Οι αλλαγές αποθηκεύονται με έξυπνο debounce (400ms) και ενημερώνουν ακαριαία το φύλλο του παίκτη μέσω WebSocket!</li>
          <li><strong>🛡️ AC Breakdown &amp; 👁️ Passive Perception:</strong> Άμεση προβολή του Armor Class (με tooltip που εξηγεί τη φόρμουλα υπολογισμού) και του Passive Perception κάθε ήρωα για κρυφούς ελέγχους.</li>
          <li><strong>🎲 DM Quick Check (Κρυφή Ζαριά DM):</strong> 6 κουμπιά (<code>STR, DEX, CON, INT, WIS, CHA</code>) πάνω στην κάρτα κάθε παίκτη που επιτρέπουν στον DM να ρίξει αμέσως Ability Check για λογαριασμό του ήρωα (χρησιμοποιώντας το πραγματικό modifier του φύλλου του) πίσω από το DM Screen!</li>
          <li><strong>🩸 Διαχείριση 14 Conditions:</strong> Ενεργοποίηση/απενεργοποίηση καταστάσεων (<em>Poisoned, Concentrating, Stunned, Unconscious, Blinded, Charmed, Frightened, Grappled, Incapacitated, Invisible, Paralyzed, Petrified, Prone, Restrained</em>) με αμφίδρομο συγχρονισμό.</li>
          <li><strong>➕ Add Member Modal (2 Τρόποι Προσθήκης):</strong> Προσθήκη μέλους στο party είτε επιλέγοντας υπάρχοντα ήρωα από το Vault (<em>Select Player Hero from Vault</em>), είτε κοινοποιώντας το 6-ψήφιο <em>Invite Code</em> στους παίκτες.</li>
        </ul>
      `,
      tags: ['dm', 'party tracker', 'online', 'hp', 'quick check', 'conditions', 'passive perception'],
    },
    {
      id: 'dm-3',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Πώς λειτουργεί το Initiative Combat Tracker (⚔️ Initiative Tab), τα Timed Conditions και τα Death Saves;',
      answerHtml: `
        <p>Η καρτέλα <strong>⚔️ Initiative Tracker</strong> είναι σχεδιασμένη για γρήγορη και ακριβή διεξαγωγή μάχης:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>👥 Import Party &amp; ➕ Add Monster:</strong> Εισαγωγή όλων των ηρώων του party με ένα κλικ (με τα τρέχοντα HP/AC τους) και γρήγορη προσθήκη custom τεράτων ή NPCs.</li>
          <li><strong>🎲 Roll All Initiative:</strong> Αυτόματη ρίψη Initiative για όλους τους μαχητές με αυτόματο <strong>DEX tie-breaking</strong> και ταξινόμηση σειράς.</li>
          <li><strong>➡️ Next / Previous Turn &amp; Mobile Alerts:</strong> Κάθε φορά που ο DM πατάει <em>Next Turn</em>, αυξάνεται ο γύρος (Round), αποθηκεύεται η κατάσταση της μάχης στο backend &amp; στο LocalStorage, και στέλνεται αυτόματα ειδοποίηση δόνησης/banner (<em>It's Your Turn!</em> / <em>On Deck</em>) στα κινητά των παικτών!</li>
          <li><strong>⏳ Timed Conditions με Αυτόματη Λήξη:</strong> Ο DM μπορεί να εφαρμόσει Condition σε οποιονδήποτε μαχητή ορίζοντας <strong>Duration in rounds</strong> (π.χ. 3 γύροι). Η αντίστροφη μέτρηση μειώνεται αυτόματα σε κάθε νέο γύρο και αφαιρεί την κατάσταση μόλις λήξει!</li>
          <li><strong>💀 Death Saves Tracker:</strong> Όταν ένας παίκτης πέσει στα <code>0 HP</code>, εμφανίζονται αυτόματα οι υποδοχές <em>Successes (1–3)</em> και <em>Failures (1–3)</em> με αυτόματη σήμανση <strong>💚 Stable</strong> ή <strong>💀 Dead</strong>.</li>
          <li><strong>⚠️ Monster Danger Indicator &amp; 📜 Statblock Modal:</strong> Αυτόματη αξιολόγηση επικινδυνότητας (<em>Low, Moderate, High, Deadly</em>) και κουμπί <strong>📜 Statblock</strong> για προβολή όλων των στατιστικών/δράσεων του τέρατος ή αναζήτηση στο D&amp;D Beyond.</li>
        </ul>
      `,
      tags: ['dm', 'initiative', 'combat', 'timed conditions', 'death saves', 'statblock', 'turn order'],
    },
    {
      id: 'dm-4',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Πώς λειτουργούν τα Roll Requests, τα Secret Rolls και το Table Inbox (💬 Whispers);',
      answerHtml: `
        <p>Η επικοινωνία και οι ζαριές ανάμεσα στον DM και τους παίκτες γίνονται σε πραγματικό χρόνο μέσω WebSockets:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🎲 Request a Roll Modal:</strong> Ο DM επιλέγει παίκτη, τύπο ζαριάς (<em>Ability Check, Skill Check, Saving Throw, Attack Roll, Initiative</em>), το αντίστοιχο Skill/Stat (π.χ. <em>Perception</em> ή <em>DEX</em>) και την αιτιολογία (π.χ. <em>Dragon Breath Fire Save</em>). Στην οθόνη του παίκτη ανοίγει αμέσως διαδραστικό prompt 30 δευτερολέπτων!</li>
          <li><strong>🔒 Secret Roll Flag &amp; Behind-the-Screen Rolls:</strong> Ο DM μπορεί είτε να μαρκάρει το αίτημα ως <em>Secret Roll</em>, είτε να ρίξει ο ίδιος κρυφά τη ζαριά από το Party Panel (<em>DM Quick Check</em>) χωρίς να εμφανιστεί τίποτα στην οθόνη του παίκτη.</li>
          <li><strong>💬 Send Whisper &amp; Broadcast:</strong> Αποστολή ιδιωτικού μηνύματος (Whisper) σε συγκεκριμένο χαρακτήρα ή ανακοίνωσης σε ολόκληρο το τραπέζι (<code>All Players</code>).</li>
          <li><strong>📥 Table Inbox Drawer:</strong> Ενοποιημένο συρτάρι ιστορικού στο κάτω μέρος της οθόνης του DM με badge μη αναγνωσμένων μηνυμάτων. Δείχνει όλα τα Whispers, την κατάσταση κάθε Roll Request (<code>Pending</code>, <code>Resolved</code> με το τελικό νούμερο, τη μαθηματική έκφραση, το Advantage/Disadvantage και τυχόν Situational Bonus, ή <code>Missed</code>), φόρμα γρήγορης απάντησης και κουμπί <strong>🚩 Report</strong> για moderation.</li>
        </ul>
      `,
      tags: ['dm', 'roll request', 'secret roll', 'whisper', 'table inbox', 'moderation'],
    },
    {
      id: 'dm-5',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Πώς δουλεύει η βάση World Lore (📚 Entities Tab), το Paste & Go AI Extractor και τα Campaign Notes;',
      answerHtml: `
        <p>Ο DM διαθέτει ένα πλήρες σύστημα αρχειοθέτησης του κόσμου της καμπάνιας:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>📚 World Lore Database (6 Κατηγορίες Οντοτήτων):</strong> Δημιουργία, επεξεργασία και διαγραφή οντοτήτων τύπου <code>Lore Note</code>, <code>NPC</code>, <code>Villain</code>, <code>Faction</code>, <code>Location</code> και <code>Monster</code>.</li>
          <li><strong>📍 Σύνδεση Τοποθεσίας &amp; Εικόνας:</strong> Κάθε NPC ή Monster μπορεί να συνδεθεί με ένα συγκεκριμένο <code>Location</code> της καμπάνιας και να συνοδεύεται από δική του εικόνα/πορτρέτο ή χάρτη (Asset Image Upload) και Markdown σημειώσεις.</li>
          <li><strong>✨ Paste &amp; Go AI Entity Extractor:</strong> Επικολλήστε οποιοδήποτε ακατέργαστο κείμενο (από σημειώσεις, περιγραφές module ή αυτοσχεδιασμό) και το AI εξάγει αυτόματα δομημένες οντότητες μαζί με τα <strong>Extracted Stats</strong> τους κατευθείαν στη βάση του campaign!</li>
          <li><strong>📝 Campaign Notes Tab:</strong> Ειδικός χώρος γρήγορων σημειώσεων (Scratchpad / Lore Notes) του DM με άμεση αποθήκευση ανά campaign.</li>
        </ul>
      `,
      tags: ['dm', 'world lore', 'entities', 'paste and go', 'npc', 'locations', 'notes'],
    },
    {
      id: 'dm-6',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Πώς λειτουργούν οι AI Γεννήτριες του DM (🎲 Encounter Generator, Quick NPC Forge & Riddles);',
      answerHtml: `
        <p>Στην καρτέλα <strong>🎲 AI Generators</strong>, ο DM μπορεί να παράγει περιεχόμενο μέσα σε δευτερόλεπτα, προσαρμοσμένο στην έκδοση κανόνων του campaign (2014 ή 2024):</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>⚔️ Random Encounter Generator:</strong> Διαβάζει αυτόματα το πλήθος των ηρώων (<code>partySize</code>) και το μέσο επίπεδό τους (<code>avgLevel</code>). Ο DM επιλέγει Δυσκολία (<em>Easy, Medium, Hard, Deadly</em>) και Περιβάλλον (π.χ. <em>Dungeon, Underdark, Forest</em>) και το AI δημιουργεί το σενάριο της μάχης και τη λίστα τεράτων με HP/AC. Με το κουμπί <strong>➕ Add to Initiative</strong>, όλα τα τέρατα μεταφέρονται αμέσως στο Initiative Tracker!</li>
          <li><strong>👤 Quick NPC Forge:</strong> Δώστε μια σύντομη ιδέα (π.χ. <em>Greedy merchant thief</em>) και το AI δημιουργεί έτοιμο NPC με εμφάνιση, κίνητρα, μυστικό και οδηγίες roleplay.</li>
          <li><strong>🧩 AI Riddle Generator:</strong> Δημιουργία θεματικών γρίφων, παγίδων και hints για dungeons.</li>
        </ul>
      `,
      tags: ['dm', 'ai generators', 'encounter generator', 'npc forge', 'riddles'],
    },
    {
      id: 'dm-7',
      category: 'dm',
      categoryLabel: 'Dungeon Master (DM)',
      badgeTone: 'gold',
      question:
        'Τι περιλαμβάνει το Session Prep (📜 Campaign Skeleton, Session Forge, Audio Chronicle & Journey Graph);',
      answerHtml: `
        <p>Η καρτέλα <strong>📜 Session Prep</strong> προσφέρει 4 πανίσχυρα εργαλεία αρχιτεκτονικής και καταγραφής συνεδριών:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>🏛️ The Campaign Skeleton (Plot Architect):</strong> Ορίστε το <em>Core Concept</em>, το <em>Tone &amp; Setting</em>, τα <em>Key Milestones</em>, τα <em>Plot Twists</em> και το <em>Max Sessions</em>. Πατώντας <strong>Generate Session Outlines</strong>, το AI σχεδιάζει ολόκληρο το πλάνο της καμπάνιας συνεδρία-προς-συνεδρία (με Main Event, Location, Required NPCs και Plot Hooks)!</li>
          <li><strong>⚔️ The Session Forge (Lazy DM Prep Architect):</strong> Συνδυάζει τις ιδέες του DM με τα προηγούμενα sessions και το ενεργό World Lore για να παράγει: <strong>🔥 Strong Start</strong>, <strong>🤫 5 Secrets &amp; Clues</strong>, <strong>⚔️ Potential Encounters</strong> και <strong>🗣️ Key NPCs</strong>.</li>
          <li><strong>🎙️ The Campaign Chronicle (Audio &amp; Text Journaling):</strong> Ανεβάστε το ηχητικό αρχείο της συνεδρίας (MP3/WAV έως 100MB με έλεγχο magic bytes) ή επικολλήστε γραπτές σημειώσεις. Το AI απομαγνητοφωνεί, δημιουργεί αναλυτικό <strong>Session Summary</strong> και εξάγει αυτόματα όλες τις νέες οντότητες (<em>Extracted Entities</em>) που εμφανίστηκαν!</li>
          <li><strong>🗺️ Party Journey Graph:</strong> Οπτικό χρονοδιάγραμμα (Interactive Node Graph) που αναλύει όλες τις καταγεγραμμένες συνεδρίες και σχεδιάζει τη διαδρομή των τοποθεσιών που επισκέφθηκε το party από το Session 1 έως σήμερα.</li>
        </ul>
      `,
      tags: ['dm', 'session prep', 'campaign skeleton', 'session forge', 'audio', 'journey graph'],
    },

    // ==========================================
    // 2. ΑΞΟΝΑΣ ΠΑΙΚΤΗ (PLAYER CAPABILITIES)
    // ==========================================
    {
      id: 'player-1',
      category: 'player',
      categoryLabel: 'Παίκτης (Player)',
      badgeTone: 'accent',
      question:
        'Ποιες είναι όλες οι δυνατότητες του Παίκτη στο Φύλλο Χαρακτήρα (Player Dashboard);',
      answerHtml: `
        <p>Το <strong>Player Dashboard (<code>/player</code>)</strong> αποτελεί το πλήρες, διαδραστικό φύλλο χαρακτήρα του παίκτη με 4 εξειδικευμένες καρτέλες:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>📜 Skills &amp; Checks:</strong> Ρίψη Ability Checks, Saving Throws και όλων των 18 Skills με ένα κλικ. Περιλαμβάνει φίλτρο <em>Proficient Only</em>, toggle proficiency/expertise και επιλογέα <strong>Advantage / Normal / Disadvantage</strong>.</li>
          <li><strong>⚔️ Combat &amp; Inventory:</strong> Πλήρης διαχείριση όπλων (Attack Roll + Damage Roll, Weapon Masteries 2024, Class Scaling Actions όπως <em>Sneak Attack</em>, <em>Divine Smite</em>, <em>Rage</em>), Class Resources (Ki/Focus Points, Second Wind, Channel Divinity), γρήγορη κατανάλωση <strong>Potions of Healing</strong> με αυτόματο roll &amp; αφαίρεση από το inventory, διαχείριση εξοπλισμού (Equipped / Attuned έως 3 αντικείμενα) και νομισμάτων (CP, SP, EP, GP, PP).</li>
          <li><strong>✨ Spells &amp; Features:</strong> Πλήρης Grimoire με φίλτρα επιπέδου (Cantrips έως 9th Level), φίλτρα <em>Prepared / Concentration / Ritual</em>, one-tap <strong>Cast Spell</strong> (με αυτόματη κατανάλωση Spell Slot ή Ritual cast χωρίς slot), Warlock Pact Magic slots, και πτυσσόμενη λίστα Features &amp; Traits.</li>
          <li><strong>📖 Lore &amp; Roleplay:</strong> Προβολή και επεξεργασία Backstory, Personality Traits, Ideals, Bonds, Flaws, Languages και Tool Proficiencies.</li>
        </ul>
      `,
      tags: ['player', 'sheet', 'skills', 'combat', 'spells', 'inventory', 'currency', 'attunement'],
    },
    {
      id: 'player-2',
      category: 'player',
      categoryLabel: 'Παίκτης (Player)',
      badgeTone: 'accent',
      question:
        'Πώς λειτουργούν τα Short Rest, Long Rest, Hit Dice, Conditions και η Επεξεργασία Φύλλου;',
      answerHtml: `
        <p>Ο παίκτης έχει πλήρη αυτονομία στη διαχείριση της κατάστασης του ήρωά του:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>⛺ Short Rest Modal:</strong> Επιλογή πόσων Hit Dice θα ξοδευτούν (με υποστήριξη multiclass διαφορετικών μεγεθών ζαριών d6/d8/d10/d12), αυτόματη ρίψη θεραπείας + CON modifier, επαναφορά Warlock Pact Magic slots και όλων των <code>short rest</code> class resources.</li>
          <li><strong>🌙 Long Rest:</strong> Πλήρης αναπλήρωση HP, επαναφορά όλων των Spell Slots, των <code>long rest</code> class resources και ανάκτηση των μισών ξοδεμένων Hit Dice.</li>
          <li><strong>🔥 Conditions &amp; Concentration Modal:</strong> Ενεργοποίηση/απενεργοποίηση καταστάσεων (Poisoned, Blinded, Prone, Charmed κ.λπ.) και δήλωση ενεργού ξορκιού Concentration.</li>
          <li><strong>✎ Edit Sheet &amp; ⚡ Quick Edit:</strong> Πλήρης επεξεργασία όλων των πεδίων του ήρωα είτε μέσω αναλυτικού modal είτε inline πάνω στο φύλλο, με optimistic locking για αποφυγή συγκρούσεων.</li>
        </ul>
      `,
      tags: ['player', 'short rest', 'long rest', 'hit dice', 'conditions', 'edit sheet'],
    },
    {
      id: 'player-3',
      category: 'player',
      categoryLabel: 'Παίκτης (Player)',
      badgeTone: 'accent',
      question:
        'Πώς αλληλεπιδρά ο Παίκτης με το Campaign και τον DM σε πραγματικό χρόνο;',
      answerHtml: `
        <p>Όταν ο χαρακτήρας συνδεθεί σε ένα Campaign μέσω <strong>🔑 Join Campaign (Invite Code)</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Real-Time WebSocket Sync:</strong> Κάθε αλλαγή HP ή Condition από τον DM ενημερώνει ακαριαία το φύλλο του παίκτη με ενημερωτικό toast.</li>
          <li><strong>🎲 DM Roll Requests:</strong> Όταν ο DM ζητήσει ζαριά (π.χ. <em>Stealth Check</em> ή <em>Wisdom Save</em>), ανοίγει διαδραστικό modal με χρονόμετρο 30 δευτερολέπτων, επιλογή Advantage/Disadvantage και Situational Bonus, στέλνοντας το αποτέλεσμα πίσω στον DM. Αν χαθεί, μπορεί να ριχτεί εκ των υστέρων από το Inbox.</li>
          <li><strong>💬 Whisper Inbox &amp; Quick Replies:</strong> Ιδιωτική συνομιλία με τον DM, προβολή ανακοινώσεων τραπεζιού (<em>All</em>), έτοιμα κουμπιά γρήγορης απάντησης και δυνατότητα Report σε μηνύματα.</li>
          <li><strong>🧪 Campaign Homebrew:</strong> Άμεση πρόσβαση και προσθήκη στο inventory/spellbook όλων των custom αντικειμένων και ξορκιών που έχει φτιάξει ο DM για το campaign.</li>
        </ul>
      `,
      tags: ['player', 'campaign', 'invite code', 'websocket', 'roll request', 'whisper'],
    },

    // ==========================================
    // 3. ΑΞΟΝΑΣ MOBILE COMPANION (#170-#175)
    // ==========================================
    {
      id: 'companion-1',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question:
        'Τι είναι το In-Person Mobile Companion και πώς προσαρμόζεται σε κινητά & tablets;',
      answerHtml: `
        <p>Σε οθόνες κινητών και tablets (<code>&lt; 1024px</code>), η εφαρμογή κρύβει αυτόματα τα βαριά εργαλεία του DM και μετατρέπεται σε <strong>In-Person Player Companion</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Bottom Action Dock (5 Tabs):</strong> Γρήγορη εναλλαγή με τον αντίχειρα ανάμεσα σε <em>Hero</em>, <em>Combat</em>, <em>Skills</em>, <em>Spells</em> και <em>Table</em> (με badge μη αναγνωσμένων μηνυμάτων) συν κεντρικό κουμπί <strong>🎲 Quick Dice</strong>.</li>
          <li><strong>Haptic Feedback &amp; Wake Lock:</strong> Φυσική ανάδραση δόνησης στις ζαριές/ζημιά και διατήρηση της οθόνης ενεργής (Screen Wake Lock) καθ' όλη τη διάρκεια της συνεδρίας.</li>
          <li><strong>Αυτόματη Επανασύνδεση:</strong> Όταν ο παίκτης ξεκλειδώνει το κινητό του, το WebSocket επανασυνδέεται αυτόματα και συγχρονίζει όσα μηνύματα ή αιτήματα ζαριών στάλθηκαν.</li>
        </ul>
      `,
      tags: ['mobile', 'companion', 'action dock', 'haptics', 'wake lock'],
    },
    {
      id: 'companion-2',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question:
        'Πώς λειτουργούν τα Turn Alerts, το Concentration Check και το Quick-Dice Drawer στο κινητό;',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>⚔️ Turn Alerts:</strong> Πράσινο παλλόμενο banner + δόνηση όταν έρχεται η σειρά του παίκτη (<em>It's Your Turn!</em>) και χρυσό banner προετοιμασίας όταν είναι επόμενος (<em>On Deck</em>).</li>
          <li><strong>🧠 Concentration Check Prompt:</strong> Κάθε φορά που ο παίκτης δέχεται ζημιά ενώ έχει ενεργό Concentration (ακόμη κι αν απορροφηθεί από Temp HP), εμφανίζεται modal με το ακριβές DC (<code>max(10, damage/2)</code>) και ρίχνει αυτόματα το CON Saving Throw (μαζί με Proficiency &amp; ενεργό Roll Mode).</li>
          <li><strong>🎲 Quick-Dice Drawer:</strong> Συρτάρι γρήγορων ζαριών (d4–d100), υποστήριξη Advantage/Disadvantage ακόμη και σε mixed pools (π.χ. <code>1d20 + 1d4</code> για <em>Guidance/Bless</em>), auto-reset roll mode και επιλογή <strong>Broadcast to DM</strong>.</li>
        </ul>
      `,
      tags: ['turn alert', 'concentration', 'quick dice', 'guidance', 'advantage'],
    },

    // ==========================================
    // 4. ΑΞΟΝΑΣ CHARACTER FORGE & IMPORTS
    // ==========================================
    {
      id: 'forge-1',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question:
        'Πώς λειτουργεί η δημιουργία χαρακτήρα (AI & Manual) και η εισαγωγή/εξαγωγή (Import/Export);',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🤖 AI Character Forge:</strong> Δημιουργία πλήρους ήρωα από ελεύθερη περιγραφή (Prompt), με αυτόματο υπολογισμό στατιστικών, ξορκιών και backstory.</li>
          <li><strong>🛠️ Manual Character Forge + AI Enrich:</strong> Βήμα-προς-βήμα φόρμα για Race, Class, Subclass, Background, Ability Scores, Skills και Spells, με επιλογή AI εμπλουτισμού.</li>
          <li><strong>📥 Multi-Platform Import:</strong> Εισαγωγή χαρακτήρων από <strong>D&amp;D Beyond</strong> (URL/ID), <strong>Foundry VTT</strong> (JSON) και επίσημα <strong>PDF Character Sheets</strong>.</li>
          <li><strong>📄 PDF Export:</strong> Εξαγωγή οποιουδήποτε χαρακτήρα σε επίσημο συμπληρωμένο PDF φύλλο χαρακτήρα με προεπισκόπηση.</li>
        </ul>
      `,
      tags: ['forge', 'ai', 'manual', 'import', 'dndbeyond', 'foundry', 'pdf'],
    },
    {
      id: 'forge-2',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question:
        'Πώς λειτουργεί το Level-Up, το Multiclassing, το Rules Validation και το AI Strategy Guide;',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>⚡ Level-Up &amp; Multiclassing Engine:</strong> Υποστήριξη ανέλιξης έως Level 20, έλεγχος προαπαιτούμενων Multiclassing, επιλογή HP (Roll ή Average), Subclass unlocks, ASI (+2 ή +1/+1) ή Feats, και αυτόματος υπολογισμός Multiclass Spellcaster Slots.</li>
          <li><strong>✅ Rules Validation &amp; Auto-Fix:</strong> Έλεγχος νομιμότητας του build απέναντι στους κανόνες 2014/2024 και αυτόματη διόρθωση (Auto-Fix) με ένα κλικ.</li>
          <li><strong>🎨 AI Portrait &amp; 🧠 Playstyle Guide:</strong> Αυτόματη δημιουργία πορτρέτου και εξατομικευμένου οδηγού τακτικής μάχης για τον χαρακτήρα.</li>
        </ul>
      `,
      tags: ['level up', 'multiclass', 'validation', 'autofix', 'portrait', 'strategy'],
    },

    // ==========================================
    // 5. ΑΞΟΝΑΣ VTT & HOMEBREW
    // ==========================================
    {
      id: 'vtt-1',
      category: 'vtt',
      categoryLabel: 'VTT & Homebrew',
      badgeTone: 'gold',
      question:
        'Πώς λειτουργεί το 2D Virtual Tabletop (VTT Grid, Scenes, Fog of War & Assets);',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🗺️ Multi-Scene Management:</strong> Ο DM μπορεί να δημιουργεί πολλαπλές σκηνές/χάρτες ανά campaign, να ανεβάζει custom χάρτες (Assets) και να αλλάζει ενεργή σκηνή ζωντανά για όλους τους παίκτες, με καταγραφή ιστορικού σκηνών (Scene History).</li>
          <li><strong>🌫️ Fog of War:</strong> Δυναμική ομίχλη πολέμου ανά κελί (Reveal / Hide cell ή Reveal All / Hide All) ώστε οι παίκτες να βλέπουν μόνο όσα δωμάτια έχουν εξερευνήσει.</li>
          <li><strong>♟️ Live Tokens:</strong> Προσθήκη tokens παικτών και εχθρών (διαφορετικών μεγεθών 1x1, 2x2 κ.λπ.), απόκρυψη αόρατων εχθρών (Hidden tokens) και drag-and-drop μετακίνηση σε πραγματικό χρόνο μέσω WebSockets.</li>
        </ul>
      `,
      tags: ['vtt', 'scenes', 'fog of war', 'tokens', 'maps', 'grid'],
    },
    {
      id: 'vtt-2',
      category: 'vtt',
      categoryLabel: 'VTT & Homebrew',
      badgeTone: 'gold',
      question: 'Πώς λειτουργεί το Homebrew Forge για τον DM και τους Παίκτες;',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>🧪 AI Homebrew Creation:</strong> Ο DM μπορεί να δημιουργήσει custom Spells, Weapons, Magic Items, Monsters και Feats περιγράφοντας την ιδέα του στο AI.</li>
          <li><strong>📡 Campaign Sharing:</strong> Κάθε Homebrew αντικείμενο που αποθηκεύεται σε ένα campaign γίνεται αμέσως διαθέσιμο στους παίκτες του campaign μέσω WebSocket για να το προσθέσουν στο φύλλο τους.</li>
          <li><strong>📦 Import / Export (JSON &amp; PDF):</strong> Εξαγωγή ολόκληρης της Homebrew βιβλιοθήκης σε εκτυπώσιμο PDF ή JSON αρχείο.</li>
        </ul>
      `,
      tags: ['homebrew', 'custom spells', 'custom items', 'monsters', 'pdf export'],
    },

    // ==========================================
    // 6. ΑΞΟΝΑΣ ΚΑΝΟΝΩΝ & AI ARBITER
    // ==========================================
    {
      id: 'rules-1',
      category: 'rules',
      categoryLabel: 'Rules & AI Arbiter',
      badgeTone: 'accent',
      question:
        'Ποιες δυνατότητες προσφέρει η Βιβλιοθήκη Κανόνων (Rules Library) και ο AI Arbiter;',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>📚 SRD Compendium:</strong> Άμεση αναζήτηση σε Classes, Subclasses, Spells, Feats, Races, Backgrounds και Equipment.</li>
          <li><strong>⚖️ 2014 Legacy vs 2024 Revision (5.5e) Comparison:</strong> Ειδικό εργαλείο AI σύγκρισης που αναλύει τις ακριβείς διαφορές ενός κανόνα, κλάσης ή ξορκιού ανάμεσα στην έκδοση 2014 και την αναθεώρηση 2024.</li>
          <li><strong>🤖 AI Rules Arbiter:</strong> Απαντά σε σύνθετες ερωτήσεις κανόνων (rulings, interactions, edge cases) λαμβάνοντας υπόψη την ενεργή έκδοση κανόνων του χρήστη.</li>
        </ul>
      `,
      tags: ['rules', 'srd', '2014', '2024', 'compare', 'ai arbiter'],
    },

    // ==========================================
    // 7. ΑΞΟΝΑΣ ADMIN & ΑΣΦΑΛΕΙΑΣ
    // ==========================================
    {
      id: 'admin-1',
      category: 'admin',
      categoryLabel: 'Admin & Ασφάλεια',
      badgeTone: 'danger',
      question:
        'Ποιες δυνατότητες ελέγχου, ασφάλειας και διαχείρισης παρέχει το Admin Workspace;',
      answerHtml: `
        <ul class="list-disc list-inside space-y-1">
          <li><strong>👤 User Management &amp; Pagination:</strong> Προβολή εγγεγραμμένων χρηστών με αναζήτηση, σελιδοποίηση (10/25/50 ανά σελίδα) και μετρητές χαρακτήρων/campaigns.</li>
          <li><strong>🟢 Live Online Presence:</strong> Ζωντανή ένδειξη <code>● Online / ○ Offline</code> που συνδυάζει ενεργές συνδέσεις WebSocket και πρόσφατη δραστηριότητα API.</li>
          <li><strong>🗑️ Cascading User Deletion με Preview:</strong> Προεπισκόπηση όλων των δεδομένων που θα επηρεαστούν πριν τη διαγραφή χρήστη (χαρακτήρες, πορτρέτα, συμμετοχές, αρχειοθέτηση whispers) και προστασία ενεργών campaigns.</li>
          <li><strong>🚩 Whisper Reports Moderation:</strong> Επιθεώρηση αναφορών (reports) με context μηνυμάτων και επίλυση (Resolved / Dismissed με σημειώσεις).</li>
          <li><strong>🔒 Ασφάλεια &amp; Rate Limiting:</strong> Προστασία JWT με έλεγχο <code>iat</code>, SlowAPI rate limiting σε Auth/AI endpoints, έλεγχος magic bytes σε uploads (PDF/Audio/Images) και αυστηρός έλεγχος δικαιωμάτων DM/Player.</li>
        </ul>
      `,
      tags: ['admin', 'pagination', 'online', 'delete cascade', 'moderation', 'security'],
    },
  ];

  filteredFaqItems = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const cat = this.selectedCategory();

    return this.faqItems.filter((item) => {
      if (!q) {
        return item.category === cat;
      }
      return (
        item.question.toLowerCase().includes(q) ||
        item.answerHtml.toLowerCase().includes(q) ||
        item.categoryLabel.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  });

  /** Questions per axis, for the counts in the category nav. */
  categoryCount(categoryId: string): number {
    return this.faqItems.filter((item) => item.category === categoryId).length;
  }

  readonly activeCategory = computed(
    () => this.categories.find((cat) => cat.id === this.selectedCategory()) ?? this.categories[0]
  );

  /** Every question in the current view is open: the toggle offers "collapse". */
  readonly allExpanded = computed(() => {
    const items = this.filteredFaqItems();
    const open = this.openQuestions();
    return items.length > 0 && items.every((item) => open.has(item.id));
  });

  toggleAll(): void {
    if (this.allExpanded()) this.collapseAll();
    else this.expandAll();
  }

  /** Category label without its leading emoji, for headings that show the icon separately. */
  categoryName(label: string): string {
    return label.replace(/^\S+\s+/, '');
  }

  isQuestionOpen(id: string): boolean {
    return this.openQuestions().has(id);
  }

  toggleQuestion(id: string): void {
    const next = new Set(this.openQuestions());
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    this.openQuestions.set(next);
  }

  expandAll(): void {
    const allIds = new Set(this.filteredFaqItems().map((i) => i.id));
    this.openQuestions.set(allIds);
  }

  collapseAll(): void {
    this.openQuestions.set(new Set());
  }

  selectCategory(catId: string): void {
    this.selectedCategory.set(catId);
    if (this.searchQuery()) {
      this.searchQuery.set('');
    }
  }
}
