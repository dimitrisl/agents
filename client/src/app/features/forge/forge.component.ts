import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { CharacterStateService } from '../../core/services/character-state.service';
import { CharacterSchema } from '../../core/models/character.model';
import { environment } from '../../../environments/environment';
import {
  ForgePageComponent,
  ForgeTab,
  ForgeTabsComponent,
} from '../../shared/ui';
import { AiFormComponent } from './ai-form/ai-form.component';
import { ManualFormComponent } from './manual-form/manual-form.component';
import { HeroPreviewComponent } from './hero-preview/hero-preview.component';

@Component({
  selector: 'app-forge',
  standalone: true,
  imports: [
    CommonModule,
    ForgePageComponent,
    ForgeTabsComponent,
    AiFormComponent,
    ManualFormComponent,
    HeroPreviewComponent,
  ],
  templateUrl: './forge.component.html',
})
export class ForgeComponent implements OnInit {
  Math = Math;
  activeTab: 'ai' | 'manual' = 'ai';
  loading = false;
  tempForgedChar: CharacterSchema | null = null;

  readonly forgeTabs: ForgeTab[] = [
    { id: 'ai', label: '✨ AI Character Forge' },
    { id: 'manual', label: '🛠️ Manual Character Builder' },
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
      ? ['Aasimar', 'Dragonborn', 'Dwarf', 'Elf', 'Gnome', 'Goliath', 'Halfling', 'Human', 'Orc', 'Tiefling', 'Warforged']
      : ['Human', 'Variant Human', 'Elf', 'Dwarf', 'Halfling', 'Dragonborn', 'Tiefling', 'Half-Orc', 'Gnome', 'Half-Elf', 'Warforged'];
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
      const map = this.is2024 ? this.subclassMap2024 : this.subclassMap2014;
      const subs = map[this.aiClass] || [];
      this.subclassOptions.push(...subs);
    }
  }

  updateManualSubclasses() {
    this.manualSubclassOptions = ['None'];
    const map = this.is2024 ? this.subclassMap2024 : this.subclassMap2014;
    const subs = map[this.manualClass] || [];
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

        // Dynamically assign an AI portrait matching chosen options if missing
        if (!char.char_portrait) {
          const promptRace = char.race || this.aiRace || 'Heroic';
          const promptClass = char.char_class || this.aiClass || 'Warrior';
          const encoded = encodeURIComponent(`epic fantasy dnd ${promptRace} ${promptClass} character portrait dramatic lighting cinematic highly detailed`);
          const seed = Math.floor(Math.random() * 90000) + 10000;
          char.char_portrait = `https://image.pollinations.ai/prompt/${encoded}?width=400&height=400&seed=${seed}&nologo=true`;
        }

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

        if (!char.char_portrait) {
          const promptRace = char.race || this.manualRace || 'Heroic';
          const promptClass = char.char_class || this.manualClass || 'Warrior';
          const encoded = encodeURIComponent(`epic fantasy dnd ${promptRace} ${promptClass} character portrait dramatic lighting cinematic highly detailed`);
          const seed = Math.floor(Math.random() * 90000) + 10000;
          char.char_portrait = `https://image.pollinations.ai/prompt/${encoded}?width=400&height=400&seed=${seed}&nologo=true`;
        }

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
        const finalChar = saved || heroToSave;
        this.charState.activeCharacter.set(finalChar);

        // Ensure character appears in local vault list immediately
        const list = this.charState.characters();
        const idx = list.findIndex((c) => c.char_id === finalChar.char_id);
        if (idx >= 0) {
          const updatedList = [...list];
          updatedList[idx] = finalChar;
          this.charState.characters.set(updatedList);
        } else {
          this.charState.characters.set([...list, finalChar]);
        }

        this.tempForgedChar = null;
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
        this.tempForgedChar = null;
        this.router.navigate(['/player']);
      }
    });
  }

  discardHero() {
    this.tempForgedChar = null;
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
