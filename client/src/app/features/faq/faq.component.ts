import { Component, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeEmptyStateComponent,
  ForgeInputDirective,
  ForgePageComponent,
} from '../../shared/ui';

export interface FaqItem {
  id: string;
  category: 'forge' | 'companion' | 'dm' | 'rules' | 'admin';
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
    ForgeCardComponent,
    ForgeEmptyStateComponent,
    ForgeInputDirective,
    ForgePageComponent,
  ],
  templateUrl: './faq.component.html',
  styleUrl: './faq.component.css',
})
export class FaqComponent {
  searchQuery = signal<string>('');
  selectedCategory = signal<string>('all');
  openQuestions = signal<Set<string>>(new Set(['forge-1', 'companion-1', 'dm-1']));

  readonly categories = [
    { id: 'all', label: '🌟 Όλα τα Θέματα', icon: '🌟' },
    { id: 'companion', label: '📱 Mobile Player Companion', icon: '📱' },
    { id: 'forge', label: '✦ Character Forge & Imports', icon: '✦' },
    { id: 'dm', label: '🏰 DM Workspace & VTT', icon: '🏰' },
    { id: 'rules', label: '📚 Rules Library & AI Arbiter', icon: '📚' },
    { id: 'admin', label: '🛡️ Admin Workspace', icon: '🛡️' },
  ];

  readonly faqItems: FaqItem[] = [
    // --- Mobile Player Companion ---
    {
      id: 'companion-1',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question: 'Τι είναι το In-Person Mobile Companion και πώς το χρησιμοποιώ στο κινητό στο φυσικό τραπέζι;',
      answerHtml: `
        <p>Το <strong>Mobile Player Companion</strong> είναι ειδικά σχεδιασμένο για ζωντανό παιχνίδι D&D γύρω από το φυσικό τραπέζι από smartphone ή tablet (&lt; 1024px).</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Bottom Action Dock:</strong> Μόνιμη μπάρα στο κάτω μέρος για άμεση πρόσβαση σε HP/Temp HP, Death Saves, Quick D20, Cast Spells, Resting, και Whisper Inbox.</li>
          <li><strong>Haptic Feedback:</strong> Δονήσεις αφής (light tap, critical success, critical failure, damage taken) για απόλυτη φυσική αίσθηση ζαριών.</li>
          <li><strong>Screen Wake Lock:</strong> Διατηρεί την οθόνη του κινητού ανοιχτή όσο παίζετε χωρίς να κλειδώνει.</li>
          <li><strong>Offline Reconnect:</strong> Επανασύνδεση και αυτόματο catch-up μηνυμάτων όταν η οθόνη του κινητού ξυπνάει (<code>visibilitychange</code>).</li>
        </ul>
      `,
      tags: ['mobile', 'companion', 'haptics', 'wake lock', 'dock', 'smartphone', 'tablet'],
    },
    {
      id: 'companion-2',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question: 'Πώς λειτουργεί το Quick-Dice Drawer και οι επιλογές Advantage / Disadvantage;',
      answerHtml: `
        <p>Πατώντας το εικονίδιο 🎲 στο Action Dock, ανοίγει το <strong>Quick-Dice Drawer</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li>Επιλογή <strong>Advantage / Normal / Disadvantage</strong> που εφαρμόζεται σε d20 αλλά και σε mixed dice pools (π.χ. <code>1d20 + 1d4</code> για <em>Bless</em> ή <em>Guidance</em>).</li>
          <li>Δυνατότητα προσθήκης πολλαπλών ζαριών (d4, d6, d8, d10, d12, d20, d100) και τροποποιητή (+/- mod).</li>
          <li>Επιλογή <strong>Broadcast to DM & Table</strong> για άμεση κοινοποίηση της ζαριάς στο live chat thread του DM.</li>
          <li>Πλήρης υποστήριξη 3D κινούμενων ζαριών με ρεαλιστική φυσική.</li>
        </ul>
      `,
      tags: ['dice', 'advantage', 'disadvantage', 'd20', 'quick-dice', 'rolls'],
    },
    {
      id: 'companion-3',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question: 'Πώς λειτουργεί η διαχείριση HP, Temp HP και ο έλεγχος Concentration (Συγκέντρωσης);',
      answerHtml: `
        <p>Στην καρτέλα Combat και στο HP Modal μπορείτε να προσθαφαιρείτε Hit Points με ασφάλεια:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Temporary HP:</strong> Απορροφούν πρώτα τη ζημιά πριν μειωθούν τα κανονικά HP.</li>
          <li><strong>Concentration Check Prompt:</strong> Σύμφωνα με τους κανόνες του D&D 5e, μόλις δεχτείτε οποιαδήποτε ζημιά ενώ συγκεντρώνεστε σε ξόρκι (ακόμη κι αν απορροφηθεί από Temp HP), εμφανίζεται άμεσα prompt με το ακριβές DC (<code>max(10, damage / 2)</code>).</li>
          <li>Πατώντας Roll Save, υπολογίζεται αυτόματα το <strong>Constitution Saving Throw bonus</strong> (μαζί με τυχόν Proficiency) και το ενεργό Advantage.</li>
          <li><strong>Death Saves:</strong> Σε 0 HP, αυτόματο tracking επιτυχιών/αποτυχιών με crit success (Natural 20 ➔ 1 HP) και crit fail (Natural 1 ➔ 2 failures).</li>
        </ul>
      `,
      tags: ['hp', 'temp hp', 'concentration', 'death saves', 'damage', 'healing'],
    },
    {
      id: 'companion-4',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question: 'Πώς ενημερώνομαι για τη σειρά μου στη μάχη (Initiative Turn Alerts);',
      answerHtml: `
        <p>Όταν ο DM ξεκινήσει encounter και προχωρήσει τους γύρους:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>It\'s Your Turn!:</strong> Εμφανίζεται πράσινο παλλόμενο banner με ηχητικό/απτικό alert ότι ήρθε η σειρά σας να ενεργήσετε.</li>
          <li><strong>On Deck:</strong> Εμφανίζεται χρυσό banner προειδοποίησης όταν είστε ο αμέσως επόμενος στο initiative, ώστε να προετοιμάσετε την κίνησή σας.</li>
        </ul>
      `,
      tags: ['turn alert', 'initiative', 'combat', 'on deck', 'dm sync'],
    },
    {
      id: 'companion-5',
      category: 'companion',
      categoryLabel: 'Mobile Companion',
      badgeTone: 'success',
      question: 'Πώς απαντώ στα Roll Requests και Whispers του DM;',
      answerHtml: `
        <p>Ο DM μπορεί να στείλει ιδιωτικό μήνυμα ή να ζητήσει ζαριά (π.χ. <em>Perception Check</em>, <em>Dexterity Save</em>):</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Live Roll Prompt:</strong> Ανοίγει αναδυόμενο παράθυρο με αντίστροφη μέτρηση 30 δευτερολέπτων, υπολογίζοντας αυτόματα το κατάλληλο modifier από το φύλλο σας.</li>
          <li><strong>Whisper Inbox:</strong> Όλα τα μυστικά μηνύματα συγκεντρώνονται σε ασφαλές chronological thread με badge μη αναγνωσμένων μηνυμάτων.</li>
          <li><strong>Report Whisper:</strong> Δυνατότητα αναφοράς ανάρμοστου μηνύματος απευθείας στους moderators/admins.</li>
        </ul>
      `,
      tags: ['whispers', 'roll request', 'inbox', 'dm', 'moderation'],
    },

    // --- Character Forge ---
    {
      id: 'forge-1',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question: 'Πώς δημιουργώ νέο χαρακτήρα και ποιες εκδόσεις κανόνων υποστηρίζονται;',
      answerHtml: `
        <p>Στο <strong>Character Forge (✦)</strong> μπορείτε να δημιουργήσετε ήρωες με δύο τρόπους:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>AI Character Generator:</strong> Περιγράψτε με απλά λόγια το concept του ήρωα (π.χ. «Ένας σκοτεινός Elf Paladin που υπηρετεί την εκδίκηση») και το AI παράγει πλήρη στατιστικά, ξόρκια, εξοπλισμό και backstory.</li>
          <li><strong>Manual Forge Form:</strong> Βήμα-προς-βήμα χειροκίνητος οδηγός επιλογής Race, Class, Background, Ability Scores (Point Buy, Standard Array, ή Rolling), Equipment και Spells.</li>
          <li><strong>2014 Legacy & 2024 Revision (5.5e):</strong> Πλήρης υποστήριξη και των δύο εκδόσεων κανόνων με αυτόματο διαχωρισμό (Subclasses, Weapon Masteries, Origin Feats).</li>
        </ul>
      `,
      tags: ['forge', 'character creation', 'ai builder', '2014', '2024', 'subclasses'],
    },
    {
      id: 'forge-2',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question: 'Πώς εισάγω χαρακτήρα από D&D Beyond, Foundry VTT ή επίσημο PDF;',
      answerHtml: `
        <p>Στο Player Dashboard πατήστε <strong>📥 Import Hero</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>D&D Beyond:</strong> Εισάγετε απλά το δημόσιο URL ή το Character ID του D&D Beyond και όλα τα στατιστικά, ξόρκια και εξοπλισμός εισάγονται αυτόματα.</li>
          <li><strong>Foundry VTT:</strong> Ανεβάστε το exported JSON αρχείο του Actor από το Foundry.</li>
          <li><strong>PDF Character Sheet:</strong> Ανεβάστε επίσημο fillable PDF φύλλο χαρακτήρα D&D 5e και το OCR/Parser σύστημα μετατρέπει τα πεδία σε ζωντανό ήρωα.</li>
        </ul>
      `,
      tags: ['import', 'dndbeyond', 'foundry', 'pdf import', 'export'],
    },
    {
      id: 'forge-3',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question: 'Πώς λειτουργεί η μηχανή Level-Up;',
      answerHtml: `
        <p>Στο Player Dashboard πατήστε <strong>⚡ Level Up</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Multiclassing:</strong> Επιλογή ανέλιξης στην κύρια κλάση ή προσθήκη νέας multiclass κλάσης με έλεγχο προαπαιτούμενων stat minimums.</li>
          <li><strong>HP Advancement:</strong> Επιλογή ανάμεσα σε σταθερό μέσο όρο (Average) ή ρίψη Hit Die με animation.</li>
          <li><strong>ASI / Feats:</strong> Επιλογή +2 Ability Score Increase, +1/+1 split, ή επιλογή Feat.</li>
          <li><strong>Spells & Features:</strong> Αυτόματος επαναϋπολογισμός Spell Slots (και multiclass caster table) και προσθήκη class features.</li>
        </ul>
      `,
      tags: ['level up', 'multiclass', 'asi', 'feats', 'hit dice'],
    },
    {
      id: 'forge-4',
      category: 'forge',
      categoryLabel: 'Character Forge',
      badgeTone: 'accent',
      question: 'Τι είναι το Rules Validation, το Auto-Fix και το AI Playstyle Guide;',
      answerHtml: `
        <p>Μέσα στο φύλλο του χαρακτήρα διατίθενται ισχυρά εργαλεία ελέγχου και βελτιστοποίησης:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Rules Validation:</strong> Ελέγχει αν ο ήρωας πληροί τους επίσημους κανόνες (π.χ. σωστά HP, νόμιμα spell slots, σωστό proficiency bonus).</li>
          <li><strong>Auto-Fix:</strong> Διορθώνει αυτόματα με ένα κλικ τυχόν παρατυπίες στα μαθηματικά ή τα στατιστικά του ήρωα.</li>
          <li><strong>AI Strategy Guide:</strong> Παράγει οδηγό στρατηγικής μάχης (action economy, spell combos, positioning) προσαρμοσμένο στα spells και abilities του ήρωα.</li>
          <li><strong>AI Portrait:</strong> Παραγωγή custom εικαστικού πορτρέτου του ήρωα με prompt generator.</li>
        </ul>
      `,
      tags: ['validation', 'autofix', 'strategy guide', 'portrait', 'rules'],
    },

    // --- DM Workspace & VTT ---
    {
      id: 'dm-1',
      category: 'dm',
      categoryLabel: 'DM Workspace',
      badgeTone: 'gold',
      question: 'Πώς λειτουργεί το DM Workspace και το Initiative Tracker;',
      answerHtml: `
        <p>Το <strong>DM Workspace (🏰)</strong> είναι το κέντρο ελέγχου της συνεδρίας για τον Dungeon Master:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Initiative Tracker:</strong> Αυτόματη ταξινόμηση παικτών και τεράτων, διαχείριση γύρων (Rounds), cycling ενεργού μαχητή και συγχρονισμός σε πραγματικό χρόνο με όλες τις οθόνες των παικτών.</li>
          <li><strong>Monster Danger Indicators:</strong> Χρωματική ένδειξη επικινδυνότητας τέρατος (Low, Medium, Deadly) σε σχέση με το επίπεδο του party.</li>
          <li><strong>Party Roster:</strong> Ζωντανή προβολή HP, AC, Passive Perception και conditions όλων των παικτών.</li>
        </ul>
      `,
      tags: ['dm', 'initiative', 'combat tracker', 'danger indicator', 'roster'],
    },
    {
      id: 'dm-2',
      category: 'dm',
      categoryLabel: 'DM Workspace',
      badgeTone: 'gold',
      question: 'Πώς λειτουργεί το Virtual Tabletop (VTT Grid, Fog of War & Tokens);',
      answerHtml: `
        <p>Ο DM μπορεί να ανοίξει το ενσωματωμένο <strong>2D Virtual Tabletop (VTT)</strong>:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>Πολλαπλές Σκηνές (Scenes):</strong> Δημιουργία χαρτών με προσαρμοσμένα background images και ρυθμιζόμενο πλέγμα (grid size).</li>
          <li><strong>Fog of War:</strong> Απόκρυψη ανεξερεύνητων περιοχών με δυναμικό εργαλείο αποκάλυψης (Reveal / Hide brush ή Reveal All).</li>
          <li><strong>Tokens:</strong> Τοποθέτηση και μετακίνηση tokens για παίκτες, NPCs και εχθρούς με αυτόματο συγχρονισμό μέσω WebSockets.</li>
        </ul>
      `,
      tags: ['vtt', 'virtual tabletop', 'fog of war', 'tokens', 'maps', 'grid'],
    },
    {
      id: 'dm-3',
      category: 'dm',
      categoryLabel: 'DM Workspace',
      badgeTone: 'gold',
      question: 'Τι είναι το Session Forge και πώς μεταγράφει ηχογραφήσεις με AI;',
      answerHtml: `
        <p>Το <strong>Session Forge</strong> αυτοματοποιεί την καταγραφή των περιπετειών σας:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li>Ανεβάστε αρχείο ήχου (mp3, wav, m4a έως 100MB) από την ηχογράφηση της ζωντανής συνεδρίας.</li>
          <li>Το AI μεταγράφει και εξάγει αυτόματα σύνοψη γεγονότων, σημαντικούς NPCs, τοποθεσίες και Journey Maps.</li>
          <li>Δημιουργεί προτάσεις Session Prep, γρίφους (Riddles) και encounters για την επόμενη συνεδρία.</li>
        </ul>
      `,
      tags: ['session forge', 'audio transcription', 'prep', 'campaign logs', 'ai audio'],
    },

    // --- Rules & AI Arbiter ---
    {
      id: 'rules-1',
      category: 'rules',
      categoryLabel: 'Rules Library',
      badgeTone: 'accent',
      question: 'Πώς λειτουργεί η Rules Library και η σύγκριση 2014 vs 2024;',
      answerHtml: `
        <p>Στη διαδρομή <strong>📚 Rules Library</strong> έχετε πρόσβαση σε πλήρη βιβλιοθήκη D&D 5e SRD:</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li>Αναζήτηση ξορκιών (Spells), τεράτων (Monsters), μαγικών αντικειμένων (Magic Items), κλάσεων και feats.</li>
          <li><strong>Rule Diff View:</strong> Άμεση σύγκριση των αλλαγών μεταξύ των κανόνων του 2014 και του 2024 Revision για κάθε ξόρκι ή μηχανισμό.</li>
          <li><strong>AI Rules Arbiter:</strong> Ρωτήστε οποιοδήποτε ερώτημα σχετικά με κανόνες σε φυσική γλώσσα (π.χ. «Μπορώ να κάνω Smite με Unarmed Strike στο 2024;») και λάβετε τεκμηριωμένη απάντηση με παραπομπές στους επίσημους κανόνες.</li>
        </ul>
      `,
      tags: ['rules', 'arbiter', 'srd', '2014 vs 2024', 'spells', 'monsters'],
    },

    // --- Admin Workspace ---
    {
      id: 'admin-1',
      category: 'admin',
      categoryLabel: 'Admin Workspace',
      badgeTone: 'danger',
      question: 'Ποιες δυνατότητες προσφέρει το Διαχειριστικό (Admin Workspace);',
      answerHtml: `
        <p>Προσβάσιμο στη διαδρομή <strong>🛡️ /admin</strong> μόνο για διαχειριστές (<code>is_admin: true</code>):</p>
        <ul class="list-disc list-inside mt-2 space-y-1">
          <li><strong>User Management:</strong> Λίστα όλων των εγγεγραμμένων χρηστών με σελιδοποίηση (Pagination: 10/25/50 ανά σελίδα) και αναζήτηση.</li>
          <li><strong>Live Status (Online/Offline):</strong> Ένδειξη σε πραγματικό χρόνο αν ο χρήστης είναι ενεργός στο σύστημα (μέσω WebSocket ή πρόσφατης δραστηριότητας).</li>
          <li><strong>Cascading Deletion:</strong> Ασφαλής διαγραφή χρήστη με προεπισκόπηση και διαγραφή των χαρακτήρων/δεδομένων του (με προστασία ενεργών DM campaigns).</li>
          <li><strong>Whisper Moderation:</strong> Έλεγχος αναφορών παραπόνων (Whisper Reports) για τοξική συμπεριφορά σε μυστικά μηνύματα.</li>
        </ul>
      `,
      tags: ['admin', 'users', 'pagination', 'online status', 'moderation', 'delete'],
    },
  ];

  filteredFaqItems = computed(() => {
    const q = this.searchQuery().trim().toLowerCase();
    const cat = this.selectedCategory();

    return this.faqItems.filter((item) => {
      const matchesCategory = cat === 'all' || item.category === cat;
      if (!matchesCategory) return false;

      if (!q) return true;
      return (
        item.question.toLowerCase().includes(q) ||
        item.answerHtml.toLowerCase().includes(q) ||
        item.tags.some((t) => t.toLowerCase().includes(q))
      );
    });
  });

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
  }
}
