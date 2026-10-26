import { Component, HostListener, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Subject, of } from 'rxjs';
import { switchMap, tap, catchError } from 'rxjs/operators';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { CharacterStateService } from '../../core/services/character-state.service';
import { DiceService } from '../../core/services/dice.service';
import { CharacterSchema } from '../../core/models/character.model';
import { environment } from '../../../environments/environment';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgePageComponent,
  ForgeTab,
  ForgeTabsComponent,
} from '../../shared/ui';
import { AiFormComponent } from './ai-form/ai-form.component';
import { ManualFormComponent } from './manual-form/manual-form.component';
import { HeroPreviewComponent } from './hero-preview/hero-preview.component';
import {
  getMaxCastableSpellLevel,
  getSubclassUnlockLevel,
  isSpellcasterClass,
} from '../../core/rules/recommendations';

const TEMP_HERO_STORAGE_KEY = 'phyrexian_forge_temp_hero';
const AI_DRAFT_STORAGE_KEY = 'phyrexian_forge_ai_draft';
const PENDING_GEN_STORAGE_KEY = 'phyrexian_forge_pending_generation';

@Component({
  selector: 'app-forge',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgePageComponent,
    ForgeTabsComponent,
    AiFormComponent,
    ManualFormComponent,
    HeroPreviewComponent,
  ],
  templateUrl: './forge.component.html',
})
export class ForgeComponent implements OnInit, OnDestroy {
  readonly subclassLockHint = 'Subclasses unlock at higher levels depending on class and edition';
  Math = Math;
  activeTab: 'ai' | 'manual' = 'ai';
  loading = false;
  tempForgedChar: CharacterSchema | null = null;
  generationInterruptedNotice = false;

  // Forging Progress Modal State
  isForgingModalOpen = false;
  forgeProgress = 0;
  forgeCurrentPhaseIndex = 0;
  forgingError: string | null = null;
  private progressInterval: any = null;
  private wakeLockSentinel: any = null;

  readonly forgePhases = [
    {
      icon: '🎲',
      title: 'Υπολογισμός Ability Scores & Modifiers',
      subtitle: 'Ρίψη ζαριών 4d6 (drop lowest) και βελτιστοποίηση πρωτευόντων στατιστικών...',
    },
    {
      icon: '⚔️',
      title: 'Επιλογή Κλάσης, Archetype & Hit Points',
      subtitle: 'Υπολογισμός Hit Dice, Armor Class, Saving Throws & Proficiencies...',
    },
    {
      icon: '✨',
      title: 'Σύνθεση Ξορκιών & Class Features',
      subtitle: 'Επιλογή Cantrips, Spells, Weapon Masteries και οργάνωση Grimoire...',
    },
    {
      icon: '📜',
      title: 'Δημιουργία Backstory & Flavor',
      subtitle: 'Σύνταξη ιστορικού, Ideals, Bonds, Flaws και χαρακτηριστικών...',
    },
    {
      icon: '🎨',
      title: 'Σχεδιασμός Πορτρέτου & Επαλήθευση Κανόνων',
      subtitle: 'Σύνθεση fantasy portrait και τελικός έλεγχος κανόνων D&D 5e / 5.5e...',
    },
    {
      icon: '✅',
      title: 'Ο Ήρωας Σφυρηλατήθηκε!',
      subtitle: 'Προετοιμασία διαδραστικού φύλλου προεπισκόπησης...',
    },
  ];

  readonly forgeTabs: ForgeTab[] = [
    { id: 'ai', label: '✨ AI Forge' },
    { id: 'manual', label: '🛠️ Manual Build' },
  ];

  // Options
  alignments = ["Lawful Good", "Neutral Good", "Chaotic Good", "Lawful Neutral", "True Neutral", "Chaotic Neutral", "Lawful Evil", "Neutral Evil", "Chaotic Evil"];
  statKeys = ["STR", "DEX", "CON", "INT", "WIS", "CHA"];
  standardArrayValues = [15, 14, 13, 12, 10, 8];

  // AI Forge Inputs
  aiRace = 'AI Choice';
  aiClass = 'AI Choice';
  aiBackground = 'AI Choice';
  aiLevel = 1;
  aiGender = 'AI Choice';
  aiSubclass = 'AI Choice';
  aiConcept = '';
  aiName = '';
  aiAlignment = 'AI Choice';
  aiUseRolled = false;

  subclassOptions = ['AI Choice'];

  // Manual Forge Inputs
  manualName = 'New Hero';
  manualLevel = 1;
  manualGender = 'Male';
  manualRace = 'Human';
  manualClass = 'Paladin';
  manualBackground = 'Soldier';
  manualAlignment = 'Lawful Good';
  manualSubclass = 'None';
  manualSubclassOptions = ['None'];
  manualConcept = '';

  manualStatMethod = 'standard';
  manualStats: Record<string, number> = { STR: 15, DEX: 14, CON: 13, INT: 12, WIS: 10, CHA: 8 };
  rolledScores: number[] = [];

  adjPlus2 = 'None';
  adjPlus1 = 'None';
  adjPlus1Alt = 'None';

  // Manual choices & rules data
  manualSkills: string[] = [];
  manualFeats: string[] = [];
  manualSpells: string[] = [];
  availableFeats: any[] = [];
  availableSpells: any[] = [];

  // Dictionaries
  // Dictionaries representing full database ruleset
  subclassMap2014: Record<string, string[]> = {
    'Artificer': ['Alchemist', 'Armorer', 'Artillerist', 'Battle Smith'],
    'Barbarian': ['Path of the Berserker', 'Path of the Totem Warrior', 'Path of the Ancestral Guardian', 'Path of the Storm Herald', 'Path of the Zealot', 'Path of the Beast', 'Path of Wild Magic'],
    'Bard': ['College of Lore', 'College of Valor', 'College of Glamour', 'College of Swords', 'College of Whispers', 'College of Creation', 'College of Eloquence', 'College of Spirits'],
    'Cleric': ['Knowledge Domain', 'Life Domain', 'Light Domain', 'Nature Domain', 'Tempest Domain', 'Trickery Domain', 'War Domain', 'Forge Domain', 'Grave Domain', 'Order Domain', 'Peace Domain', 'Twilight Domain', 'Arcana Domain', 'Death Domain'],
    'Druid': ['Circle of the Land', 'Circle of the Moon', 'Circle of Dreams', 'Circle of the Shepherd', 'Circle of Spores', 'Circle of Stars', 'Circle of Wildfire'],
    'Fighter': ['Champion', 'Battle Master', 'Eldritch Knight', 'Arcane Archer', 'Cavalier', 'Samurai', 'Echo Knight', 'Psi Warrior', 'Rune Knight'],
    'Monk': ['Way of the Open Hand', 'Way of Shadow', 'Way of the Four Elements', 'Way of the Long Death', 'Way of the Sun Soul', 'Way of the Drunken Master', 'Way of the Kensei', 'Way of the Astral Self', 'Way of the Mercy', 'Way of the Ascendant Dragon'],
    'Paladin': ['Oath of Devotion', 'Oath of the Ancients', 'Oath of Vengeance', 'Oath of the Crown', 'Oath of Conquest', 'Oath of Redemption', 'Oath of Glory', 'Oath of the Watchers', 'Oathbreaker'],
    'Ranger': ['Hunter', 'Beast Master', 'Gloom Stalker', 'Horizon Walker', 'Monster Slayer', 'Fey Wanderer', 'Swarmkeeper', 'Drakewarden'],
    'Rogue': ['Thief', 'Assassin', 'Arcane Trickster', 'Inquisitive', 'Mastermind', 'Scout', 'Swashbuckler', 'Phantom', 'Soulknife'],
    'Sorcerer': ['Draconic Bloodline', 'Wild Magic', 'Divine Soul', 'Shadow Magic', 'Storm Sorcery', 'Aberrant Mind', 'Clockwork Soul'],
    'Warlock': ['The Archfey', 'The Fiend', 'The Great Old One', 'The Undying', 'The Celestial', 'The Hexblade', 'The Fathomless', 'The Genie', 'The Undead'],
    'Wizard': ['School of Abjuration', 'School of Conjuration', 'School of Divination', 'School of Enchantment', 'School of Evocation', 'School of Illusion', 'School of Necromancy', 'School of Transmutation', 'Bladesinging', 'War Magic', 'Chronurgy Magic', 'Graviturgy Magic', 'Order of Scribes']
  };

  subclassMap2024: Record<string, string[]> = {
    'Artificer': ['Alchemist', 'Armorer', 'Artillerist', 'Battle Smith', 'Cartographer'],
    'Barbarian': ['Path of the Berserker', 'Path of the Wild Heart', 'Path of the World Tree', 'Path of the Zealot'],
    'Bard': ['College of Dance', 'College of Glamour', 'College of Lore', 'College of Valor'],
    'Cleric': ['Life Domain', 'Light Domain', 'Trickery Domain', 'War Domain'],
    'Druid': ['Circle of the Land', 'Circle of the Moon', 'Circle of the Sea', 'Circle of the Stars'],
    'Fighter': ['Battle Master', 'Champion', 'Eldritch Knight', 'Psi Warrior'],
    'Monk': ['Warrior of Mercy', 'Warrior of Shadow', 'Warrior of the Elements', 'Warrior of the Open Hand'],
    'Paladin': ['Oath of Devotion', 'Oath of Glory', 'Oath of the Ancients', 'Oath of Vengeance'],
    'Ranger': ['Beast Master', 'Fey Wanderer', 'Gloom Stalker', 'Hunter'],
    'Rogue': ['Arcane Trickster', 'Assassin', 'Soulknife', 'Thief'],
    'Sorcerer': ['Aberrant Sorcery', 'Clockwork Sorcery', 'Draconic Sorcery', 'Wild Magic'],
    'Warlock': ['Archfey Patron', 'Celestial Patron', 'Fiend Patron', 'Great Old One Patron'],
    'Wizard': ['Abjurer', 'Diviner', 'Evoker', 'Illusionist']
  };

  classColors: Record<string, string> = {
    'Barbarian': '#e74c3c', 'Bard': '#9b59b6', 'Cleric': '#f1c40f', 'Druid': '#2ecc71',
    'Fighter': '#e67e22', 'Monk': '#1abc9c', 'Paladin': '#f39c12', 'Ranger': '#27ae60',
    'Rogue': '#95a5a6', 'Sorcerer': '#ff6b6b', 'Warlock': '#8e44ad', 'Wizard': '#3498db'
  };

  primaryStatsMap: Record<string, string[]> = {
    'Barbarian': ['STR', 'CON'], 'Bard': ['CHA'], 'Cleric': ['WIS'], 'Druid': ['WIS'],
    'Fighter': ['STR', 'DEX'], 'Monk': ['DEX', 'WIS'], 'Paladin': ['STR', 'CHA'],
    'Ranger': ['DEX', 'WIS'], 'Rogue': ['DEX'], 'Sorcerer': ['CHA'], 'Warlock': ['CHA'], 'Wizard': ['INT']
  };

  constructor(
    public charState: CharacterStateService,
    private dice: DiceService,
    private http: HttpClient,
    private router: Router
  ) {}

  @HostListener('window:beforeunload', ['$event'])
  onBeforeUnload(event: BeforeUnloadEvent): void {
    if (this.loading || (this.isForgingModalOpen && !this.forgingError)) {
      event.preventDefault();
      event.returnValue = '';
    }
  }

  ngOnInit() {
    this.restoreAiDraft();
    this.restoreTempHero();
    this.checkPendingGenerationRecovery();
    this.updateSubclasses();
    this.updateManualSubclasses();
    this.fetchFeats();
    this.fetchSpells();
  }

  ngOnDestroy(): void {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
    }
    this.releaseWakeLock();
  }

  saveAiDraft(): void {
    try {
      if (typeof localStorage === 'undefined') return;
      const draft = {
        aiRace: this.aiRace,
        aiClass: this.aiClass,
        aiBackground: this.aiBackground,
        aiLevel: this.aiLevel,
        aiGender: this.aiGender,
        aiSubclass: this.aiSubclass,
        aiConcept: this.aiConcept,
        aiName: this.aiName,
        aiAlignment: this.aiAlignment,
        aiUseRolled: this.aiUseRolled,
      };
      localStorage.setItem(AI_DRAFT_STORAGE_KEY, JSON.stringify(draft));
    } catch {}
  }

  restoreAiDraft(): void {
    try {
      if (typeof localStorage === 'undefined') return;
      const saved = localStorage.getItem(AI_DRAFT_STORAGE_KEY);
      if (saved) {
        const draft = JSON.parse(saved);
        if (draft.aiRace) this.aiRace = draft.aiRace;
        if (draft.aiClass) this.aiClass = draft.aiClass;
        if (draft.aiBackground) this.aiBackground = draft.aiBackground;
        if (draft.aiLevel) this.aiLevel = draft.aiLevel;
        if (draft.aiGender) this.aiGender = draft.aiGender;
        if (draft.aiSubclass) this.aiSubclass = draft.aiSubclass;
        if (draft.aiConcept) this.aiConcept = draft.aiConcept;
        if (draft.aiName) this.aiName = draft.aiName;
        if (draft.aiAlignment) this.aiAlignment = draft.aiAlignment;
        if (typeof draft.aiUseRolled === 'boolean') this.aiUseRolled = draft.aiUseRolled;
      }
    } catch {}
  }

  saveTempHero(char: CharacterSchema): void {
    this.tempForgedChar = char;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(TEMP_HERO_STORAGE_KEY, JSON.stringify(char));
      }
    } catch {}
  }

  restoreTempHero(): void {
    try {
      if (typeof localStorage === 'undefined') return;
      const saved = localStorage.getItem(TEMP_HERO_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed && typeof parsed === 'object' && parsed.stats && typeof parsed.stats === 'object') {
          this.tempForgedChar = parsed;
        }
      }
    } catch {}
  }

  clearTempHero(): void {
    this.tempForgedChar = null;
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(TEMP_HERO_STORAGE_KEY);
      }
    } catch {}
  }

  startPendingGeneration(): void {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(PENDING_GEN_STORAGE_KEY, Date.now().toString());
      }
    } catch {}
  }

  clearPendingGeneration(): void {
    try {
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem(PENDING_GEN_STORAGE_KEY);
      }
    } catch {}
  }

  checkPendingGenerationRecovery(): void {
    try {
      if (typeof localStorage === 'undefined') return;
      const pendingTimeStr = localStorage.getItem(PENDING_GEN_STORAGE_KEY);
      if (pendingTimeStr && !this.tempForgedChar) {
        const elapsed = Date.now() - parseInt(pendingTimeStr, 10);
        if (elapsed < 3 * 60 * 1000) {
          this.generationInterruptedNotice = true;
        }
        this.clearPendingGeneration();
      }
    } catch {}
  }

  private async requestWakeLock(): Promise<void> {
    if (typeof navigator !== 'undefined' && 'wakeLock' in navigator) {
      try {
        this.wakeLockSentinel = await (navigator as any).wakeLock.request('screen');
      } catch {
        // WakeLock may be rejected on low battery or inactive tabs; ignore safely
      }
    }
  }

  private releaseWakeLock(): void {
    if (this.wakeLockSentinel) {
      try {
        this.wakeLockSentinel.release().catch(() => {});
      } catch {}
      this.wakeLockSentinel = null;
    }
  }

  toggleEditionAndRefresh() {
    this.charState.toggleEdition();
    this.manualFeats = [];
    this.manualSpells = [];
    if (!this.raceOptions.includes(this.manualRace)) {
      this.manualRace = this.raceOptions[0] || 'Human';
    }
    if (!this.bgOptions.includes(this.manualBackground)) {
      this.manualBackground = this.bgOptions[0] || 'Soldier';
    }
    this.updateSubclasses();
    this.updateManualSubclasses();
    this.fetchFeats();
    this.fetchSpells();
  }

  onManualClassChange(newClass?: string) {
    if (newClass !== undefined) {
      this.manualClass = newClass;
    }
    this.manualSkills = [];
    this.manualFeats = [];
    this.manualSpells = [];
    this.updateManualSubclasses();
    this.fetchSpells();
  }

  onManualLevelChange(newLevel?: number) {
    if (newLevel !== undefined) {
      this.manualLevel = Number(newLevel);
    }
    this.updateManualSubclasses();
    if (!isSpellcasterClass(this.manualClass, this.manualSubclass, this.manualLevel, this.is2024)) {
      this.manualSpells = [];
    } else {
      const maxLvl = getMaxCastableSpellLevel(
        this.manualClass,
        this.manualLevel,
        this.is2024,
        this.manualSubclass
      );
      this.manualSpells = this.manualSpells.filter((spellName) => {
        const found = this.availableSpells.find((s) => s.name === spellName);
        return !found || (found.level ?? 0) <= maxLvl;
      });
    }
    this.fetchSpells();
  }

  onManualSubclassChange(newSubclass?: string) {
    if (newSubclass !== undefined) {
      this.manualSubclass = newSubclass;
    }
    if (!isSpellcasterClass(this.manualClass, this.manualSubclass, this.manualLevel, this.is2024)) {
      this.manualSpells = [];
    }
    this.fetchSpells();
  }

  fetchFeats() {
    this.http.get<any[]>(`${environment.apiBaseUrl}/rules/feats`, {
      params: { edition: this.charState.dndEdition() }
    }).subscribe({
      next: (feats) => this.availableFeats = feats || [],
      error: () => this.availableFeats = []
    });
  }

  fetchSpells() {
    const c = (this.manualClass || '').toLowerCase();
    const sub = (this.manualSubclass || '').toLowerCase();
    let spellClass = this.manualClass;
    if (
      (c === 'fighter' && sub.includes('eldritch knight')) ||
      (c === 'rogue' && sub.includes('arcane trickster'))
    ) {
      spellClass = 'Wizard';
    }

    this.http.get<any[]>(`${environment.apiBaseUrl}/rules/spells`, {
      params: {
        edition: this.charState.dndEdition(),
        char_class: spellClass,
        char_level: this.manualLevel
      }
    }).subscribe({
      next: (spells) => this.availableSpells = spells || [],
      error: () => this.availableSpells = []
    });
  }

  get is2024(): boolean {
    return this.charState.dndEdition().includes('2024');
  }

  get raceOptions(): string[] {
    return this.is2024
      ? ['Aasimar', 'Dragonborn', 'Dwarf', 'Elf', 'Gnome', 'Goliath', 'Halfling', 'Human', 'Orc', 'Tiefling', 'Warforged']
      : ['Human', 'Variant Human', 'Elf', 'Dwarf', 'Halfling', 'Dragonborn', 'Tiefling', 'Half-Orc', 'Gnome', 'Half-Elf', 'Warforged'];
  }

  get classOptions(): string[] {
    return ['Barbarian', 'Bard', 'Cleric', 'Druid', 'Fighter', 'Monk', 'Paladin', 'Ranger', 'Rogue', 'Sorcerer', 'Warlock', 'Wizard'];
  }

  get bgOptions(): string[] {
    return ['Acolyte', 'Charlatan', 'Criminal', 'Entertainer', 'Folk Hero', 'Guild Artisan', 'Hermit', 'Noble', 'Outlander', 'Sage', 'Sailor', 'Soldier', 'Urchin', 'Custom Background'];
  }

  // --- Blueprint side panel (presentation only, derived from the form state) ---

  get blueprintName(): string {
    const name = ((this.activeTab === 'ai' ? this.aiName : this.manualName) || '').trim();
    return name || 'Unnamed Hero';
  }

  get blueprintSubtitle(): string {
    const race = this.activeTab === 'ai' ? this.aiRace : this.manualRace;
    const charClass = this.activeTab === 'ai' ? this.aiClass : this.manualClass;
    const parts = [race, charClass].filter((v) => v && v !== 'AI Choice' && v !== 'None');
    return parts.length ? parts.join(' · ') : 'The forge will decide the details';
  }

  get blueprintLevel(): number {
    return this.activeTab === 'ai' ? this.aiLevel : this.manualLevel;
  }

  getSubclassMinLevel(charClass: string): number {
    return getSubclassUnlockLevel(charClass, this.is2024);
  }

  get aiSubclassLocked(): boolean {
    return Number(this.aiLevel || 1) < this.getSubclassMinLevel(this.aiClass);
  }

  get manualSubclassLocked(): boolean {
    return Number(this.manualLevel || 1) < this.getSubclassMinLevel(this.manualClass);
  }

  get aiSubclassLockHint(): string {
    return this.getSubclassLockHint(this.aiClass);
  }

  get manualSubclassLockHint(): string {
    return this.getSubclassLockHint(this.manualClass);
  }

  getSubclassLockHint(charClass: string): string {
    const minLevel = this.getSubclassMinLevel(charClass);
    const className = charClass && charClass !== 'AI Choice' ? charClass : 'Class';
    if (this.is2024) {
      return `${className} subclass unlocks at Level ${minLevel} (2024 rules).`;
    }
    return `${className} subclass unlocks at Level ${minLevel} (2014 rules).`;
  }

  get blueprintStatsMode(): string {
    if (this.activeTab === 'ai') return this.aiUseRolled ? 'Rolled 4d6' : 'Standard Array';
    if (this.manualStatMethod === 'rolled') return 'Rolled 4d6';
    if (this.manualStatMethod === 'custom') return 'Custom';
    return 'Standard Array';
  }

  get blueprintRows(): { label: string; value: string; auto: boolean }[] {
    const speciesLabel = this.is2024 ? 'Species' : 'Race';
    const rows =
      this.activeTab === 'ai'
        ? [
            { label: speciesLabel, value: this.aiRace },
            { label: 'Class', value: this.aiClass },
            { label: 'Subclass', value: this.aiSubclass },
            { label: 'Background', value: this.aiBackground },
            { label: 'Alignment', value: this.aiAlignment },
            { label: 'Gender', value: this.aiGender },
          ]
        : [
            { label: speciesLabel, value: this.manualRace },
            { label: 'Class', value: this.manualClass },
            { label: 'Subclass', value: this.manualSubclass },
            { label: 'Background', value: this.manualBackground },
            { label: 'Alignment', value: this.manualAlignment },
            { label: 'Gender', value: this.manualGender },
          ];

    const placeholder = this.activeTab === 'ai' ? 'AI decides' : 'Not set';
    return rows.map(({ label, value }) => {
      const auto = !value || value === 'AI Choice' || value === 'None';
      return { label, value: auto ? placeholder : value, auto };
    });
  }

  trackBlueprintRow(_index: number, row: { label: string }): string {
    return row.label;
  }

  updateSubclasses() {
    this.subclassOptions = ['AI Choice'];
    if (this.aiSubclassLocked) {
      this.aiSubclass = 'AI Choice';
      return;
    }
    if (this.aiClass !== 'AI Choice') {
      const map = this.is2024 ? this.subclassMap2024 : this.subclassMap2014;
      const subs = map[this.aiClass] || [];
      this.subclassOptions.push(...subs);
    }
  }

  updateManualSubclasses() {
    this.manualSubclassOptions = ['None'];
    if (this.manualSubclassLocked) {
      this.manualSubclass = 'None';
      return;
    }
    const map = this.is2024 ? this.subclassMap2024 : this.subclassMap2014;
    const subs = map[this.manualClass] || [];
    this.manualSubclassOptions.push(...subs);
    if (!this.manualSubclassOptions.includes(this.manualSubclass)) {
      this.manualSubclass = 'None';
    }
  }

  roll4d6Stats() {
    this.rolledScores = this.dice.rollAbilityScores(6);
    this.statKeys.forEach((k, idx) => {
      this.manualStats[k] = this.rolledScores[idx] || 10;
    });
  }

  getFinalStat(key: string): number {
    let base = Number(this.manualStats[key]) || 10;
    if (this.adjPlus2 === key) base += 2;
    if (this.adjPlus1 === key) base += 1;
    if (this.adjPlus1Alt === key) base += 1;
    return base;
  }

  startForgingProgress(): void {
    this.isForgingModalOpen = true;
    this.forgeProgress = 3;
    this.forgeCurrentPhaseIndex = 0;
    this.forgingError = null;
    this.requestWakeLock();
    this.startPendingGeneration();

    if (this.progressInterval) {
      clearInterval(this.progressInterval);
    }

    const startTime = Date.now();
    this.progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime;

      if (elapsed < 3000) {
        // Phase 0: 3% -> 20%
        this.forgeCurrentPhaseIndex = 0;
        this.forgeProgress = Math.min(20, Math.floor(3 + (elapsed / 3000) * 17));
      } else if (elapsed < 6500) {
        // Phase 1: 20% -> 42%
        this.forgeCurrentPhaseIndex = 1;
        this.forgeProgress = Math.min(42, Math.floor(20 + ((elapsed - 3000) / 3500) * 22));
      } else if (elapsed < 10000) {
        // Phase 2: 42% -> 65%
        this.forgeCurrentPhaseIndex = 2;
        this.forgeProgress = Math.min(65, Math.floor(42 + ((elapsed - 6500) / 3500) * 23));
      } else if (elapsed < 13500) {
        // Phase 3: 65% -> 82%
        this.forgeCurrentPhaseIndex = 3;
        this.forgeProgress = Math.min(82, Math.floor(65 + ((elapsed - 10000) / 3500) * 17));
      } else if (elapsed < 17000) {
        // Phase 4: 82% -> 92%
        this.forgeCurrentPhaseIndex = 4;
        this.forgeProgress = Math.min(92, Math.floor(82 + ((elapsed - 13500) / 3500) * 10));
      } else {
        // Decelerating smoothly towards 95% while waiting for LLM
        this.forgeCurrentPhaseIndex = 4;
        if (this.forgeProgress < 95) {
          this.forgeProgress = Math.min(95, Math.round((this.forgeProgress + 0.2) * 10) / 10);
        }
      }
    }, 150);
  }

  finishForgingProgress(char: CharacterSchema): void {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
    this.forgeProgress = 100;
    this.forgeCurrentPhaseIndex = 5;
    this.saveTempHero(char);
    this.clearPendingGeneration();
    this.releaseWakeLock();

    setTimeout(() => {
      this.loading = false;
      this.isForgingModalOpen = false;
    }, 600);
  }

  handleForgingError(err?: any): void {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
    this.loading = false;
    this.clearPendingGeneration();
    this.releaseWakeLock();
    this.forgingError =
      err?.error?.detail ||
      'Παρουσιάστηκε σφάλμα κατά τη σφυρηλάτηση ή εξαντλήθηκε το όριο αιτημάτων. Παρακαλούμε δοκιμάστε ξανά.';
  }

  closeForgingModal(): void {
    if (this.progressInterval) {
      clearInterval(this.progressInterval);
      this.progressInterval = null;
    }
    this.loading = false;
    this.isForgingModalOpen = false;
    this.forgingError = null;
    this.releaseWakeLock();
    this.clearPendingGeneration();
  }

  retryForging(): void {
    if (this.activeTab === 'manual') {
      this.createManualCharacter();
    } else {
      this.generateAiCharacter();
    }
  }

  generateAiCharacter() {
    if (this.loading) return;
    this.loading = true;
    this.saveAiDraft();
    this.startForgingProgress();

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/forge/generate`, {
      concept: this.aiConcept,
      target_level: this.aiLevel,
      char_class: this.aiClass,
      race: this.aiRace,
      background: this.aiBackground,
      gender: this.aiGender,
      name: this.aiName || 'AI Choice',
      alignment: this.aiAlignment,
      stats_mode: this.aiUseRolled ? 'rolled' : 'standard',
      subclass: !this.aiSubclassLocked && this.aiSubclass !== 'AI Choice' ? this.aiSubclass : null,
      edition: this.charState.dndEdition()
    }).subscribe({
      next: (char) => {
        // Dynamically assign an AI portrait matching chosen options if missing
        if (!char.char_portrait) {
          const promptRace = char.race || this.aiRace || 'Heroic';
          const promptClass = char.char_class || this.aiClass || 'Warrior';
          const encoded = encodeURIComponent(`epic fantasy dnd ${promptRace} ${promptClass} character portrait dramatic lighting cinematic highly detailed`);
          const seed = Math.floor(Math.random() * 90000) + 10000;
          char.char_portrait = `https://image.pollinations.ai/prompt/${encoded}?width=400&height=400&seed=${seed}&nologo=true`;
        }

        this.finishForgingProgress(char);
      },
      error: (err) => {
        this.handleForgingError(err);
      }
    });
  }

  createManualCharacter() {
    if (this.loading) return;
    this.loading = true;
    this.startForgingProgress();

    const finalStats: Record<string, number> = {};
    this.statKeys.forEach((k) => (finalStats[k] = this.getFinalStat(k)));

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/forge/enrich-manual`, {
      name: this.manualName,
      char_class: this.manualClass,
      race: this.manualRace,
      target_level: this.manualLevel,
      background: this.manualBackground,
      subclass: !this.manualSubclassLocked && this.manualSubclass !== 'None' ? this.manualSubclass : null,
      alignment: this.manualAlignment,
      gender: this.manualGender,
      concept: this.manualConcept,
      base_stats: finalStats,
      edition: this.charState.dndEdition(),
      skill_proficiencies: this.manualSkills,
      chosen_feats: this.manualFeats.length > 0 ? this.manualFeats : null,
      chosen_spells: this.manualSpells.length > 0 ? this.manualSpells : null,
    }).subscribe({
      next: (char) => {
        if (!char.char_portrait) {
          const promptRace = char.race || this.manualRace || 'Heroic';
          const promptClass = char.char_class || this.manualClass || 'Warrior';
          const encoded = encodeURIComponent(`epic fantasy dnd ${promptRace} ${promptClass} character portrait dramatic lighting cinematic highly detailed`);
          const seed = Math.floor(Math.random() * 90000) + 10000;
          char.char_portrait = `https://image.pollinations.ai/prompt/${encoded}?width=400&height=400&seed=${seed}&nologo=true`;
        }

        this.finishForgingProgress(char);
      },
      error: (err) => {
        this.handleForgingError(err);
      }
    });
  }

  regeneratePortrait() {
    if (!this.tempForgedChar) return;
    const promptRace = this.tempForgedChar.race || 'Heroic';
    const promptClass = this.tempForgedChar.char_class || 'Warrior';
    const encoded = encodeURIComponent(`epic fantasy dnd ${promptRace} ${promptClass} character portrait dramatic lighting cinematic highly detailed`);
    const seed = Math.floor(Math.random() * 90000) + 10000;

    // Instant high quality fallback portrait update
    this.tempForgedChar.char_portrait = `https://image.pollinations.ai/prompt/${encoded}?width=400&height=400&seed=${seed}&nologo=true`;

    this.http.post<any>(`${environment.apiBaseUrl}/forge/portrait`, {
      char_id: this.tempForgedChar.char_id || 'temp',
      force: true
    }).subscribe({
      next: (res) => {
        if (res && res.portrait_url && this.tempForgedChar) {
          this.tempForgedChar.char_portrait = res.portrait_url;
          this.saveTempHero(this.tempForgedChar);
        }
      },
      error: () => {}
    });
  }

  acceptAndEquipHero() {
    if (!this.tempForgedChar) return;
    this.loading = true;
    const heroToSave = { ...this.tempForgedChar };

    this.charState.saveCharacter(heroToSave).subscribe({
      next: (saved) => {
        this.loading = false;

        // saveCharacter already equipped the hero and put them in the vault list;
        // this only covers an API that answered without a body.
        if (!saved) {
          this.charState.activeCharacter.set(heroToSave);
          this.charState.characters.set([...this.charState.characters(), heroToSave]);
        }

        this.clearTempHero();
        this.router.navigate(['/player']);
      },
      error: (err) => {
        this.loading = false;
        console.error('Failed to save character to DB:', err);
        alert('Error saving character to database. Check console for details. ' + (err.error?.detail || err.message));

        // Force local fallback so player can still play, but warn them
        this.charState.activeCharacter.set(heroToSave);
        const list = this.charState.characters();
        this.charState.characters.set([...list, heroToSave]);
        this.clearTempHero();
        this.router.navigate(['/player']);
      }
    });
  }

  discardHero() {
    this.clearTempHero();
  }

  getClassColor(charClass: string): string {
    return this.classColors[charClass] || '#f39c12';
  }

  isPrimaryStat(charClass: string, stat: string): boolean {
    const primary = this.primaryStatsMap[charClass] || [];
    return primary.includes(stat);
  }

  getModifierString(val: number): string {
    const mod = Math.floor((val - 10) / 2);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }
}
