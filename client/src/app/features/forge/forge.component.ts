import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { CharacterStateService } from '../../core/services/character-state.service';
import { CharacterSchema } from '../../core/models/character.model';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-forge',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="forge-container">
      <h2 class="forge-title">Forge a New Hero</h2>

      <!-- 1. FORGE FORM VIEW (If no temp forged character) -->
      <div *ngIf="!tempForgedChar" class="phyrexian-card forge-card">
        <div class="nav-tabs">
          <div class="tab-item" [class.active]="activeTab === 'ai'" (click)="activeTab = 'ai'">✨ AI Character Forge</div>
          <div class="tab-item" [class.active]="activeTab === 'manual'" (click)="activeTab = 'manual'">🛠️ Manual Character Builder</div>
        </div>

        <!-- TAB 1: AI CHARACTER FORGE -->
        <div *ngIf="activeTab === 'ai'" class="tab-body">
          <p class="guide-text">Choose your core pillars or let the AI decide!</p>

          <div class="inner-box">
            <!-- Row 1: Race, Class, Background -->
            <div class="form-row">
              <div>
                <label>{{ is2024 ? 'Species' : 'Race' }}</label>
                <select class="phyrexian-select" [(ngModel)]="aiRace">
                  <option value="AI Choice">AI Choice</option>
                  <option *ngFor="let r of raceOptions" [value]="r">{{ r }}</option>
                </select>
              </div>
              <div>
                <label>Class</label>
                <select class="phyrexian-select" [(ngModel)]="aiClass" (change)="updateSubclasses()">
                  <option value="AI Choice">AI Choice</option>
                  <option *ngFor="let c of classOptions" [value]="c">{{ c }}</option>
                </select>
              </div>
              <div>
                <label>Background</label>
                <select class="phyrexian-select" [(ngModel)]="aiBackground">
                  <option value="AI Choice">AI Choice</option>
                  <option *ngFor="let b of bgOptions" [value]="b">{{ b }}</option>
                </select>
              </div>
            </div>

            <!-- Row 2: Level, Gender, Subclass -->
            <div class="form-row">
              <div>
                <label>Target Level</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="aiLevel" min="1" max="20" (change)="updateSubclasses()" />
              </div>
              <div>
                <label>Gender</label>
                <select class="phyrexian-select" [(ngModel)]="aiGender">
                  <option value="AI Choice">AI Choice</option>
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Non-binary">Non-binary</option>
                  <option value="Other">Other</option>
                </select>
              </div>
              <div>
                <label>Subclass</label>
                <select class="phyrexian-select" [(ngModel)]="aiSubclass" [disabled]="subclassOptions.length <= 1">
                  <option *ngFor="let s of subclassOptions" [value]="s">{{ s }}</option>
                </select>
              </div>
            </div>

            <!-- Concept Textarea -->
            <div class="form-group">
              <label>Additional Flavor / Concept:</label>
              <textarea class="phyrexian-textarea" rows="3" [(ngModel)]="aiConcept" placeholder="E.g., A grumpy baker who uses a massive rolling pin as a weapon."></textarea>
            </div>

            <!-- Row 3: Name, Alignment, Rolled Stats Toggle -->
            <div class="form-row align-center">
              <div>
                <label>Character Name (optional)</label>
                <input type="text" class="phyrexian-input" [(ngModel)]="aiName" placeholder="AI Choice" />
              </div>
              <div>
                <label>Alignment</label>
                <select class="phyrexian-select" [(ngModel)]="aiAlignment">
                  <option value="AI Choice">AI Choice</option>
                  <option *ngFor="let a of alignments" [value]="a">{{ a }}</option>
                </select>
              </div>
              <div class="toggle-col">
                <label class="toggle-label">
                  <input type="checkbox" [(ngModel)]="aiUseRolled" />
                  🎲 Use Rolled Stats (4d6 drop lowest)
                </label>
              </div>
            </div>

            <button class="phyrexian-btn full-btn submit-forge-btn" [disabled]="loading" (click)="generateAiCharacter()">
              {{ loading ? '⏳ Forging Character...' : 'Generate Character' }}
            </button>
          </div>
        </div>

        <!-- TAB 2: MANUAL CHARACTER BUILDER -->
        <div *ngIf="activeTab === 'manual'" class="tab-body">
          <p class="guide-text">Build your character step-by-step manually. The system handles all rules calculations!</p>

          <div class="inner-box">
            <!-- 1. Basic Info -->
            <div class="form-row">
              <div>
                <label>Character Name</label>
                <input type="text" class="phyrexian-input" [(ngModel)]="manualName" />
              </div>
              <div>
                <label>Level</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="manualLevel" min="1" max="20" (change)="updateManualSubclasses()" />
              </div>
              <div>
                <label>Gender</label>
                <select class="phyrexian-select" [(ngModel)]="manualGender">
                  <option value="Male">Male</option>
                  <option value="Female">Female</option>
                  <option value="Non-binary">Non-binary</option>
                  <option value="Other">Other</option>
                </select>
              </div>
            </div>

            <!-- 2. Pillars -->
            <div class="form-row">
              <div>
                <label>{{ is2024 ? 'Species' : 'Race' }}</label>
                <select class="phyrexian-select" [(ngModel)]="manualRace">
                  <option *ngFor="let r of raceOptions" [value]="r">{{ r }}</option>
                </select>
              </div>
              <div>
                <label>Class</label>
                <select class="phyrexian-select" [(ngModel)]="manualClass" (change)="updateManualSubclasses()">
                  <option *ngFor="let c of classOptions" [value]="c">{{ c }}</option>
                </select>
              </div>
              <div>
                <label>Background</label>
                <select class="phyrexian-select" [(ngModel)]="manualBackground">
                  <option *ngFor="let b of bgOptions" [value]="b">{{ b }}</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div>
                <label>Alignment</label>
                <select class="phyrexian-select" [(ngModel)]="manualAlignment">
                  <option *ngFor="let a of alignments" [value]="a">{{ a }}</option>
                </select>
              </div>
              <div>
                <label>Subclass</label>
                <select class="phyrexian-select" [(ngModel)]="manualSubclass">
                  <option *ngFor="let s of manualSubclassOptions" [value]="s">{{ s }}</option>
                </select>
              </div>
            </div>

            <!-- Concept -->
            <div class="form-group">
              <label>Additional Flavor / Concept / Backstory Idea:</label>
              <textarea class="phyrexian-textarea" rows="2" [(ngModel)]="manualConcept" placeholder="E.g., A dwarf blacksmith seeking his ancestor's anvil."></textarea>
            </div>

            <hr class="divider" />

            <!-- 🎲 Ability Score Allocation -->
            <h4 class="section-subheading">🎲 Base Ability Scores</h4>
            <div class="form-group">
              <label>Allocation Method:</label>
              <select class="phyrexian-select" [(ngModel)]="manualStatMethod">
                <option value="standard">Standard Array (15, 14, 13, 12, 10, 8)</option>
                <option value="rolled">Roll for Stats (4d6 drop lowest)</option>
                <option value="custom">Manual Entry / Custom</option>
              </select>
            </div>

            <!-- Standard Array Allocation -->
            <div *ngIf="manualStatMethod === 'standard'" class="stats-allocation-grid">
              <div *ngFor="let stat of statKeys">
                <label>{{ stat }}</label>
                <select class="phyrexian-select" [(ngModel)]="manualStats[stat]">
                  <option *ngFor="let val of standardArrayValues" [value]="val">{{ val }}</option>
                </select>
              </div>
            </div>

            <!-- Rolled Stats Allocation -->
            <div *ngIf="manualStatMethod === 'rolled'" class="rolled-stats-section">
              <button class="phyrexian-btn-secondary" (click)="roll4d6Stats()">🎲 Roll 6 Stats (4d6 drop lowest)</button>
              <p *ngIf="rolledScores.length > 0" class="rolled-display">
                Rolled Scores: <strong>{{ rolledScores.join(', ') }}</strong>
              </p>
              <div *ngIf="rolledScores.length > 0" class="stats-allocation-grid">
                <div *ngFor="let stat of statKeys">
                  <label>{{ stat }}</label>
                  <select class="phyrexian-select" [(ngModel)]="manualStats[stat]">
                    <option *ngFor="let val of rolledScores" [value]="val">{{ val }}</option>
                  </select>
                </div>
              </div>
            </div>

            <!-- Custom Entry -->
            <div *ngIf="manualStatMethod === 'custom'" class="stats-allocation-grid">
              <div *ngFor="let stat of statKeys">
                <label>{{ stat }}</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="manualStats[stat]" min="3" max="30" />
              </div>
            </div>

            <!-- Adjustments (+2 / +1) -->
            <h4 class="section-subheading" style="margin-top: 1rem;">📈 Ability Score Adjustments (+2 / +1)</h4>
            <div class="form-row">
              <div>
                <label>+2 Bonus to:</label>
                <select class="phyrexian-select" [(ngModel)]="adjPlus2">
                  <option value="None">None</option>
                  <option *ngFor="let s of statKeys" [value]="s">{{ s }}</option>
                </select>
              </div>
              <div>
                <label>+1 Bonus to:</label>
                <select class="phyrexian-select" [(ngModel)]="adjPlus1">
                  <option value="None">None</option>
                  <option *ngFor="let s of statKeys" [value]="s">{{ s }}</option>
                </select>
              </div>
              <div>
                <label>Alt +1 Bonus to:</label>
                <select class="phyrexian-select" [(ngModel)]="adjPlus1Alt">
                  <option value="None">None</option>
                  <option *ngFor="let s of statKeys" [value]="s">{{ s }}</option>
                </select>
              </div>
            </div>

            <!-- Calculated Final Scores -->
            <div class="final-stats-bar">
              <strong>Final Ability Scores:</strong>
              <div class="final-stats-inline">
                <span *ngFor="let s of statKeys">
                  <strong>{{ s }}:</strong> {{ getFinalStat(s) }} ({{ getModifierString(getFinalStat(s)) }})
                </span>
              </div>
            </div>

            <button class="phyrexian-btn full-btn submit-forge-btn" [disabled]="loading" (click)="createManualCharacter()">
              {{ loading ? 'Compiling Rules...' : 'Create Character' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 2. 🔍 HERO PREVIEW SCREEN (Streamlit Replica) -->
      <div *ngIf="tempForgedChar" class="phyrexian-card preview-card">
        <h3 class="preview-heading">🔍 Hero Preview</h3>

        <div class="preview-layout">
          <!-- Left Column (70%) -->
          <div class="preview-info">
            <div class="edit-name-group">
              <label>✏️ Edit Hero Name:</label>
              <input type="text" class="phyrexian-input hero-name-input" [(ngModel)]="tempForgedChar.char_name" />
            </div>

            <!-- Header Badges -->
            <div class="badges-row">
              <span class="class-pill" [style.background]="getClassColor(tempForgedChar.char_class)">
                Level {{ tempForgedChar.char_level }} {{ tempForgedChar.char_class }}
                <ng-container *ngIf="tempForgedChar.subclass">({{ tempForgedChar.subclass }})</ng-container>
              </span>
              <span class="meta-pill">{{ tempForgedChar.race }}</span>
              <span class="meta-pill">{{ tempForgedChar.background }}</span>
              <span class="edition-pill">{{ tempForgedChar.dnd_edition || charState.dndEdition() }}</span>
            </div>

            <!-- Derived Combat Metrics Bar -->
            <div class="metrics-bar">
              <div class="metric-item">
                <span class="m-label">❤️ MAX HP</span>
                <span class="m-val hp-val">{{ tempForgedChar.hp_max }}</span>
              </div>
              <div class="metric-item">
                <span class="m-label">🛡️ ARMOR CLASS</span>
                <span class="m-val ac-val">{{ tempForgedChar.armor_class }}</span>
              </div>
              <div class="metric-item">
                <span class="m-label">⚡ INITIATIVE</span>
                <span class="m-val init-val">{{ getModifierString(tempForgedChar.stats.DEX || 10) }}</span>
              </div>
              <div class="metric-item">
                <span class="m-label">👁️ PASSIVE PERC</span>
                <span class="m-val perc-val">{{ 10 + Math.floor(((tempForgedChar.stats.WIS || 10) - 10) / 2) }}</span>
              </div>
            </div>

            <!-- 6 Stat Badges with Primary Class Highlights -->
            <div class="stats-badges-grid">
              <div
                *ngFor="let s of statKeys"
                class="stat-badge-card"
                [class.primary-stat]="isPrimaryStat(tempForgedChar.char_class, s)"
                [style.border-color]="isPrimaryStat(tempForgedChar.char_class, s) ? getClassColor(tempForgedChar.char_class) : 'rgba(255,255,255,0.12)'">
                <span class="s-name" [style.color]="isPrimaryStat(tempForgedChar.char_class, s) ? getClassColor(tempForgedChar.char_class) : '#888'">
                  {{ isPrimaryStat(tempForgedChar.char_class, s) ? '⭐ ' : '' }}{{ s }}
                </span>
                <span class="s-val">{{ tempForgedChar.stats[s] || 10 }}</span>
                <span class="s-mod">({{ getModifierString(tempForgedChar.stats[s] || 10) }})</span>
              </div>
            </div>

            <!-- Backstory Quote -->
            <div *ngIf="tempForgedChar.backstory" class="backstory-quote" [style.border-left-color]="getClassColor(tempForgedChar.char_class)">
              "{{ tempForgedChar.backstory }}"
            </div>
          </div>

          <!-- Right Column (30%): Portrait -->
          <div class="preview-portrait">
            <img [src]="tempForgedChar.char_portrait || 'assets/anvil.png'" alt="Portrait" class="portrait-image" />
            <button class="phyrexian-btn-secondary full-btn" style="margin-top: 0.75rem;" (click)="regeneratePortrait()">
              🔄 Regenerate Portrait
            </button>
          </div>
        </div>

        <!-- Action Bar -->
        <div class="preview-actions">
          <button class="phyrexian-btn accept-btn" (click)="acceptAndEquipHero()">
            ✅ Accept & Equip Hero
          </button>
          <button class="phyrexian-btn-secondary discard-btn" (click)="tempForgedChar = null">
            ❌ Discard
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .forge-container { max-width: 900px; margin: 0 auto; padding-bottom: 2rem; }
    .forge-title { color: var(--theme-accent); margin-bottom: 1rem; }
    .guide-text { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 1rem; }
    .inner-box { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-card); padding: 1.25rem; border-radius: 8px; }
    .form-row { display: flex; gap: 1rem; margin-bottom: 1rem; }
    .form-row div { flex: 1; }
    .form-group { margin-bottom: 1rem; }
    .form-group label, .form-row label { display: block; margin-bottom: 0.3rem; font-size: 0.85rem; color: var(--text-muted); }
    .align-center { align-items: flex-end; }
    .toggle-col { display: flex; align-items: center; height: 38px; }
    .toggle-label { font-size: 0.85rem; color: var(--text-primary); cursor: pointer; }
    .submit-forge-btn { margin-top: 1rem; padding: 0.8rem; font-size: 1.05rem; }
    .divider { border: none; border-top: 1px solid var(--border-card); margin: 1.5rem 0; }
    .section-subheading { color: var(--text-gold); font-size: 1rem; margin-bottom: 0.75rem; }
    .stats-allocation-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.5rem; margin-bottom: 1rem; }
    .rolled-display { font-size: 0.9rem; color: var(--text-gold); margin: 0.5rem 0; }
    .final-stats-bar { background: rgba(255, 255, 255, 0.05); padding: 0.75rem; border-radius: 6px; margin: 1rem 0; font-size: 0.85rem; }
    .final-stats-inline { display: flex; gap: 1rem; margin-top: 0.3rem; flex-wrap: wrap; }
    /* Preview Screen Styling */
    .preview-heading { color: var(--text-gold); font-size: 1.4rem; margin-bottom: 1.25rem; }
    .preview-layout { display: flex; gap: 1.5rem; }
    .preview-info { flex: 7; }
    .preview-portrait { flex: 3; text-align: center; }
    .portrait-image { width: 100%; max-height: 280px; object-fit: cover; border-radius: 8px; border: 2px solid var(--theme-accent); }
    .edit-name-group { margin-bottom: 1rem; }
    .hero-name-input { font-size: 1.4rem; font-weight: 700; color: var(--theme-accent); }
    .badges-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .class-pill { padding: 0.3rem 0.8rem; border-radius: 14px; font-weight: 700; font-size: 0.85rem; color: #fff; }
    .meta-pill { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); padding: 0.3rem 0.8rem; border-radius: 14px; font-size: 0.85rem; }
    .edition-pill { background: rgba(52,152,219,0.18); color: #3498db; border: 1px solid rgba(52,152,219,0.4); padding: 0.3rem 0.8rem; border-radius: 14px; font-size: 0.85rem; font-weight: 700; }
    .metrics-bar { display: flex; background: rgba(0,0,0,0.4); border: 1px solid var(--border-card); border-radius: 8px; padding: 0.75rem; text-align: center; margin-bottom: 1rem; }
    .metric-item { flex: 1; border-right: 1px solid rgba(255,255,255,0.1); }
    .metric-item:last-child { border-right: none; }
    .m-label { display: block; font-size: 0.7rem; color: var(--text-muted); font-weight: 700; }
    .m-val { font-size: 1.2rem; font-weight: 800; }
    .hp-val { color: #e74c3c; }
    .ac-val { color: #f39c12; }
    .init-val { color: #3498db; }
    .perc-val { color: #2ecc71; }
    .stats-badges-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.5rem; margin-bottom: 1rem; }
    .stat-badge-card { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 0.5rem; text-align: center; }
    .stat-badge-card.primary-stat { background: rgba(255,255,255,0.08); }
    .s-name { display: block; font-size: 0.7rem; font-weight: 700; }
    .s-val { font-size: 1.25rem; font-weight: 800; color: #fff; }
    .s-mod { font-size: 0.75rem; color: var(--text-gold); font-weight: 700; }
    .backstory-quote { background: rgba(0,0,0,0.3); border-left: 3px solid var(--theme-accent); padding: 0.8rem 1rem; border-radius: 4px; font-style: italic; font-size: 0.88rem; line-height: 1.4; color: #ccc; margin-bottom: 1rem; }
    .preview-actions { display: flex; gap: 1rem; margin-top: 1.5rem; }
    .accept-btn { flex: 1; justify-content: center; padding: 0.8rem; font-size: 1.05rem; }
    .discard-btn { flex: 1; justify-content: center; padding: 0.8rem; font-size: 1.05rem; }
    .full-btn { width: 100%; }
  `]
})
export class ForgeComponent implements OnInit {
  Math = Math;
  activeTab: 'ai' | 'manual' = 'ai';
  loading = false;
  tempForgedChar: CharacterSchema | null = null;

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

  // Dictionaries
  subclassMap2014: Record<string, string[]> = {
    'Artificer': ['Alchemist', 'Armorer', 'Artillerist', 'Battle Smith'],
    'Barbarian': ['Path of the Berserker', 'Path of the Totem Warrior', 'Path of the Zealot'],
    'Bard': ['College of Lore', 'College of Valor', 'College of Glamour'],
    'Cleric': ['Life Domain', 'Light Domain', 'Trickery Domain', 'War Domain'],
    'Druid': ['Circle of the Land', 'Circle of the Moon'],
    'Fighter': ['Champion', 'Battle Master', 'Eldritch Knight'],
    'Monk': ['Way of the Open Hand', 'Way of Shadow'],
    'Paladin': ['Oath of Devotion', 'Oath of Vengeance'],
    'Ranger': ['Hunter', 'Beast Master', 'Gloom Stalker'],
    'Rogue': ['Thief', 'Assassin', 'Arcane Trickster'],
    'Sorcerer': ['Draconic Bloodline', 'Wild Magic'],
    'Warlock': ['The Fiend', 'The Archfey', 'The Great Old One'],
    'Wizard': ['School of Evocation', 'School of Abjuration']
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
    private http: HttpClient,
    private router: Router
  ) {}

  ngOnInit() {
    this.updateSubclasses();
    this.updateManualSubclasses();
  }

  get is2024(): boolean {
    return this.charState.dndEdition().includes('2024');
  }

  get raceOptions(): string[] {
    return this.is2024
      ? ['Aasimar', 'Dragonborn', 'Dwarf', 'Elf', 'Gnome', 'Goliath', 'Halfling', 'Human', 'Orc', 'Tiefling']
      : ['Human', 'Variant Human', 'Elf', 'Dwarf', 'Halfling', 'Dragonborn', 'Tiefling', 'Half-Orc', 'Gnome', 'Half-Elf'];
  }

  get classOptions(): string[] {
    return ['Barbarian', 'Bard', 'Cleric', 'Druid', 'Fighter', 'Monk', 'Paladin', 'Ranger', 'Rogue', 'Sorcerer', 'Warlock', 'Wizard'];
  }

  get bgOptions(): string[] {
    return ['Acolyte', 'Charlatan', 'Criminal', 'Entertainer', 'Folk Hero', 'Guild Artisan', 'Hermit', 'Noble', 'Outlander', 'Sage', 'Sailor', 'Soldier', 'Urchin'];
  }

  updateSubclasses() {
    this.subclassOptions = ['AI Choice'];
    if (this.aiClass !== 'AI Choice') {
      const subs = this.subclassMap2014[this.aiClass] || [];
      this.subclassOptions.push(...subs);
    }
  }

  updateManualSubclasses() {
    this.manualSubclassOptions = ['None'];
    const subs = this.subclassMap2014[this.manualClass] || [];
    this.manualSubclassOptions.push(...subs);
  }

  roll4d6Stats() {
    const rolled: number[] = [];
    for (let i = 0; i < 6; i++) {
      const dice = Array.from({ length: 4 }, () => Math.floor(Math.random() * 6) + 1);
      dice.sort((a, b) => a - b);
      rolled.push(dice[1] + dice[2] + dice[3]);
    }
    this.rolledScores = rolled.sort((a, b) => b - a);
    this.statKeys.forEach((k, idx) => {
      this.manualStats[k] = this.rolledScores[idx] || 10;
    });
  }

  getFinalStat(key: string): number {
    let base = this.manualStats[key] || 10;
    if (this.adjPlus2 === key) base += 2;
    if (this.adjPlus1 === key) base += 1;
    if (this.adjPlus1Alt === key) base += 1;
    return base;
  }

  generateAiCharacter() {
    this.loading = true;
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
      subclass: this.aiSubclass !== 'AI Choice' ? this.aiSubclass : null,
      edition: this.charState.dndEdition()
    }).subscribe({
      next: (char) => {
        this.loading = false;
        this.tempForgedChar = char;
      },
      error: () => {
        this.loading = false;
        alert('Failed to generate character.');
      }
    });
  }

  createManualCharacter() {
    this.loading = true;
    const finalStats: Record<string, number> = {};
    this.statKeys.forEach((k) => (finalStats[k] = this.getFinalStat(k)));

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/forge/enrich-manual`, {
      name: this.manualName,
      char_class: this.manualClass,
      race: this.manualRace,
      target_level: this.manualLevel,
      background: this.manualBackground,
      subclass: this.manualSubclass !== 'None' ? this.manualSubclass : null,
      alignment: this.manualAlignment,
      gender: this.manualGender,
      concept: this.manualConcept,
      base_stats: finalStats,
      edition: this.charState.dndEdition()
    }).subscribe({
      next: (char) => {
        this.loading = false;
        this.tempForgedChar = char;
      },
      error: () => {
        this.loading = false;
        alert('Failed to create manual character.');
      }
    });
  }

  regeneratePortrait() {
    if (!this.tempForgedChar) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/portrait`, {
      char_id: this.tempForgedChar.char_id || 'temp',
      prompt: `${this.tempForgedChar.race} ${this.tempForgedChar.char_class}`
    }).subscribe((res) => {
      if (res.portrait_url && this.tempForgedChar) {
        this.tempForgedChar.char_portrait = res.portrait_url;
      }
    });
  }

  acceptAndEquipHero() {
    if (!this.tempForgedChar) return;
    this.charState.saveCharacter(this.tempForgedChar).subscribe(() => {
      this.tempForgedChar = null;
      this.router.navigate(['/player']);
    });
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
