import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterStateService } from '../../core/services/character-state.service';
import { CharacterSchema } from '../../core/models/character.model';

@Component({
  selector: 'app-player',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="player-container">
      <!-- Character Vault Header -->
      <div class="phyrexian-card vault-bar">
        <div class="vault-selector">
          <label>📜 Select Character:</label>
          <select
            class="phyrexian-select"
            [ngModel]="charState.activeCharacter()?.char_id"
            (ngModelChange)="onSelectCharacter($event)">
            <option *ngFor="let c of charState.characters()" [value]="c.char_id">
              {{ c.char_name }} (Lvl {{ c.char_level }} {{ c.char_class }})
            </option>
          </select>
        </div>

        <div class="vault-actions">
          <button class="phyrexian-btn" (click)="activeTab = 'sheet'">🗡️ Sheet</button>
          <button class="phyrexian-btn-secondary" (click)="activeTab = 'creator'">✨ New Hero</button>
          <button class="phyrexian-btn-secondary" (click)="activeTab = 'levelup'">⚡ Level Up</button>
        </div>
      </div>

      <!-- Main Character Sheet Content -->
      <ng-container *ngIf="activeTab === 'sheet' && charState.activeCharacter() as char">
        <!-- Vitals Banner -->
        <div class="phyrexian-card vitals-grid">
          <div class="char-portrait">
            <img [src]="char.char_portrait || 'assets/anvil.png'" alt="Portrait" class="portrait-img" />
          </div>
          <div class="vitals-info">
            <h2>{{ char.char_name }}</h2>
            <p class="subtitle">{{ char.race }} {{ char.char_class }} ({{ char.subclass || 'No Subclass' }}) • Level {{ char.char_level }}</p>

            <div class="vitals-boxes">
              <div class="stat-box">
                <span class="stat-label">Armor Class</span>
                <span class="stat-value">🛡️ {{ char.armor_class }}</span>
              </div>
              <div class="stat-box">
                <span class="stat-label">Hit Points</span>
                <span class="stat-value">❤️ {{ char.hp_current ?? char.hp_max }} / {{ char.hp_max }}</span>
              </div>
              <div class="stat-box">
                <span class="stat-label">Prof. Bonus</span>
                <span class="stat-value">+{{ char.proficiency_bonus }}</span>
              </div>
              <div class="stat-box">
                <span class="stat-label">Speed</span>
                <span class="stat-value">👟 {{ char.speed }} ft</span>
              </div>
              <div class="stat-box">
                <span class="stat-label">Passive Perception</span>
                <span class="stat-value">👁️ {{ charState.passivePerception() }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Ability Scores Grid -->
        <div class="stats-grid">
          <div class="stat-box" *ngFor="let entry of getStatsArray(char.stats)">
            <span class="stat-label">{{ entry.key }}</span>
            <span class="stat-value">{{ entry.value }}</span>
            <span class="stat-mod">({{ getModifierString(entry.value) }})</span>
          </div>
        </div>

        <!-- Tabs Navigation -->
        <div class="nav-tabs">
          <div class="tab-item" [class.active]="sheetSubTab === 'combat'" (click)="sheetSubTab = 'combat'">⚔️ Combat & Inventory</div>
          <div class="tab-item" [class.active]="sheetSubTab === 'spells'" (click)="sheetSubTab = 'spells'">✨ Spells & Features</div>
          <div class="tab-item" [class.active]="sheetSubTab === 'roleplay'" (click)="sheetSubTab = 'roleplay'">📖 Lore & Roleplay</div>
        </div>

        <!-- Subtab 1: Combat & Inventory -->
        <div *ngIf="sheetSubTab === 'combat'" class="phyrexian-card">
          <h3>⚔️ Equipped Weapons & Attacks</h3>
          <table class="weapons-table">
            <thead>
              <tr>
                <th>Weapon</th>
                <th>To Hit</th>
                <th>Damage</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let w of char.weapons">
                <td><strong>{{ w.name }}</strong></td>
                <td><span class="hit-badge">{{ w.attack_bonus }}</span></td>
                <td>{{ w.damage_dice }} {{ w.damage_bonus }}</td>
              </tr>
            </tbody>
          </table>

          <h3 style="margin-top: 1.5rem;">🎒 Inventory</h3>
          <ul>
            <li *ngFor="let item of char.equipment">{{ item.name }} (Equipped: {{ item.equipped ? 'Yes' : 'No' }})</li>
          </ul>
        </div>

        <!-- Subtab 2: Spells & Features -->
        <div *ngIf="sheetSubTab === 'spells'" class="phyrexian-card">
          <h3>🌟 Features & Traits</h3>
          <div class="features-list">
            <div class="feature-card" *ngFor="let f of char.features_traits">
              <h4>{{ f.name }}</h4>
              <p>{{ f.description }}</p>
            </div>
          </div>
        </div>

        <!-- Subtab 3: Roleplay -->
        <div *ngIf="sheetSubTab === 'roleplay'" class="phyrexian-card">
          <h3>📖 Backstory</h3>
          <p>{{ char.backstory || 'No backstory recorded.' }}</p>
        </div>
      </ng-container>
    </div>
  `,
  styles: [`
    .vault-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .vault-selector {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .vault-actions {
      display: flex;
      gap: 0.5rem;
    }
    .vitals-grid {
      display: flex;
      gap: 1.5rem;
      margin-bottom: 1.5rem;
    }
    .portrait-img {
      width: 120px;
      height: 120px;
      object-fit: cover;
      border-radius: 8px;
      border: 2px solid var(--theme-accent);
    }
    .vitals-info {
      flex: 1;
    }
    .subtitle {
      color: var(--text-muted);
      margin-bottom: 1rem;
    }
    .vitals-boxes {
      display: flex;
      gap: 1rem;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    .weapons-table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 0.5rem;
    }
    .weapons-table th, .weapons-table td {
      padding: 0.6rem;
      text-align: left;
      border-bottom: 1px solid var(--border-card);
    }
    .hit-badge {
      background: var(--theme-accent);
      color: #fff;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
    }
    .feature-card {
      background: rgba(0, 0, 0, 0.3);
      border: 1px solid var(--border-card);
      padding: 0.8rem;
      border-radius: 6px;
      margin-top: 0.5rem;
    }
  `]
})
export class PlayerComponent implements OnInit {
  activeTab: 'sheet' | 'creator' | 'levelup' = 'sheet';
  sheetSubTab: 'combat' | 'spells' | 'roleplay' = 'combat';

  constructor(public charState: CharacterStateService) {}

  ngOnInit() {
    this.charState.loadCharacters().subscribe();
  }

  onSelectCharacter(charId: string) {
    const selected = this.charState.characters().find((c) => c.char_id === charId);
    if (selected) {
      this.charState.activeCharacter.set(selected);
    }
  }

  getStatsArray(stats: any) {
    if (!stats) return [];
    return Object.keys(stats).map((key) => ({ key, value: stats[key] }));
  }

  getModifierString(val: number): string {
    const mod = Math.floor((val - 10) / 2);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }
}
