import { Component, OnInit, effect, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { WebSocketService, WsMessage } from '../../core/services/websocket.service';
import { CharacterSchema, Weapon, EquipmentItem } from '../../core/models/character.model';
import { DiceRollerComponent } from '../../shared/components/dice-roller/dice-roller.component';
import { environment } from '../../../environments/environment';

export interface SkillDefinition {
  name: string;
  ability: 'STR' | 'DEX' | 'CON' | 'INT' | 'WIS' | 'CHA';
}

@Component({
  selector: 'app-player',
  standalone: true,
  imports: [CommonModule, FormsModule, DiceRollerComponent],
  template: `
    <div class="player-container">
      <!-- Top Action & Vault Bar -->
      <div class="phyrexian-card vault-bar">
        <div class="vault-selector">
          <label>📜 Hero Vault:</label>
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
          <button class="phyrexian-btn" (click)="goToForge()">✨ New Hero</button>
          <button class="phyrexian-btn-secondary" (click)="openEditModal()">✏️ Edit Sheet</button>
          <button class="phyrexian-btn-secondary" (click)="toggleEditMode()">
            {{ editMode ? '💾 Done Editing' : '⚡ Quick Edit' }}
          </button>
          <button class="phyrexian-btn-secondary" (click)="showJoinModal = true">🔑 Join Campaign</button>
        </div>
      </div>

      <!-- Main Character Sheet Content -->
      <ng-container *ngIf="charState.activeCharacter() as char; else emptyState">
        <!-- Active Campaign Indicator -->
        <div *ngIf="char.active_campaign" class="campaign-indicator">
          🏰 Member of Campaign: <strong>{{ char.active_campaign }}</strong>
        </div>

        <!-- Vitals Header Banner -->
        <div class="phyrexian-card vitals-grid">
          <div class="char-portrait" (click)="showPortraitModal = true">
            <img [src]="getPortraitUrl(char)" alt="Portrait" class="portrait-img" />
            <div class="portrait-overlay">📷 AI Portrait</div>
          </div>

          <div class="vitals-info">
            <div class="hero-name-row">
              <h2 *ngIf="!editMode">{{ char.char_name }}</h2>
              <input *ngIf="editMode" type="text" class="phyrexian-input name-input" [(ngModel)]="char.char_name" (ngModelChange)="saveCurrentChar()" />
              <span class="edition-pill">{{ char.dnd_edition || charState.dndEdition() }}</span>
            </div>

            <p *ngIf="!editMode" class="subtitle">
              {{ char.race }} {{ char.char_class }} ({{ char.subclass || 'No Subclass' }}) • Level {{ char.char_level }} • {{ char.background }}
            </p>
            <div *ngIf="editMode" class="edit-basics-row">
              <input type="text" class="phyrexian-input" [(ngModel)]="char.race" placeholder="Race" (ngModelChange)="saveCurrentChar()" />
              <input type="text" class="phyrexian-input" [(ngModel)]="char.char_class" placeholder="Class" (ngModelChange)="saveCurrentChar()" />
              <input type="text" class="phyrexian-input" [(ngModel)]="char.subclass" placeholder="Subclass" (ngModelChange)="saveCurrentChar()" />
              <input type="number" class="phyrexian-input" [(ngModel)]="char.char_level" placeholder="Level" (ngModelChange)="saveCurrentChar()" />
              <input type="text" class="phyrexian-input" [(ngModel)]="char.background" placeholder="Background" (ngModelChange)="saveCurrentChar()" />
            </div>

            <div class="vitals-boxes">
              <div class="stat-box">
                <span class="stat-label">Armor Class</span>
                <span *ngIf="!editMode" class="stat-value">🛡️ {{ char.armor_class }}</span>
                <input *ngIf="editMode" type="number" class="phyrexian-input mini-input" [(ngModel)]="char.armor_class" (ngModelChange)="saveCurrentChar()" />
              </div>

              <div class="stat-box hp-box">
                <span class="stat-label">Hit Points</span>
                <div class="hp-controls">
                  <button class="hp-btn" (click)="adjustHp(-1)">-</button>
                  <span class="stat-value">❤️ {{ char.hp_current ?? char.hp_max }} / {{ char.hp_max }}</span>
                  <button class="hp-btn" (click)="adjustHp(1)">+</button>
                </div>
              </div>

              <div class="stat-box">
                <span class="stat-label">Hit Dice</span>
                <span class="stat-value">🎲 {{ getAvailableHitDice() }} / {{ char.char_level }}</span>
                <span class="stat-mod">(d{{ getClassHitDieSize() }})</span>
              </div>

              <div class="stat-box">
                <span class="stat-label">Prof. Bonus</span>
                <span class="stat-value">+{{ char.proficiency_bonus }}</span>
              </div>
              <div class="stat-box">
                <span class="stat-label">Speed</span>
                <span *ngIf="!editMode" class="stat-value">👟 {{ char.speed }} ft</span>
                <input *ngIf="editMode" type="number" class="phyrexian-input mini-input" [(ngModel)]="char.speed" (ngModelChange)="saveCurrentChar()" />
              </div>
              <div class="stat-box">
                <span class="stat-label">Passive Perception</span>
                <span class="stat-value">👁️ {{ charState.passivePerception() }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 6 Ability Scores Grid -->
        <div class="stats-grid">
          <div class="stat-box" *ngFor="let entry of getStatsArray(char.stats)">
            <span class="stat-label">{{ entry.key }}</span>
            <span *ngIf="!editMode" class="stat-value">{{ entry.value }}</span>
            <input *ngIf="editMode" type="number" class="phyrexian-input mini-input" [(ngModel)]="char.stats[entry.key]" (ngModelChange)="saveCurrentChar()" />
            <span class="stat-mod">({{ getModifierString(char.stats[entry.key]) }})</span>

            <div class="stat-roll-btns">
              <button class="phyrexian-btn-secondary mini-roll-btn" (click)="rollAbilityCheck(entry.key)">
                Check
              </button>
              <button class="phyrexian-btn-secondary mini-roll-btn save-btn" (click)="rollSavingThrow(entry.key)">
                Save
              </button>
            </div>
          </div>
        </div>

        <!-- Roll Mode Advantage Selector -->
        <div class="phyrexian-card roll-mode-bar">
          <label>🎲 Roll Advantage Mode:</label>
          <div class="roll-mode-options">
            <label class="radio-label">
              <input type="radio" name="rollMode" value="normal" [(ngModel)]="rollMode" /> Normal
            </label>
            <label class="radio-label">
              <input type="radio" name="rollMode" value="advantage" [(ngModel)]="rollMode" /> Advantage ⚡
            </label>
            <label class="radio-label">
              <input type="radio" name="rollMode" value="disadvantage" [(ngModel)]="rollMode" /> Disadvantage ⚠️
            </label>
          </div>
        </div>

        <!-- Sheet Tabs Navigation -->
        <div class="nav-tabs">
          <div class="tab-item" [class.active]="sheetSubTab === 'skills'" (click)="sheetSubTab = 'skills'">📜 Skills & Checks</div>
          <div class="tab-item" [class.active]="sheetSubTab === 'combat'" (click)="sheetSubTab = 'combat'">⚔️ Combat & Inventory</div>
          <div class="tab-item" [class.active]="sheetSubTab === 'spells'" (click)="sheetSubTab = 'spells'">✨ Spells & Features</div>
          <div class="tab-item" [class.active]="sheetSubTab === 'roleplay'" (click)="sheetSubTab = 'roleplay'">📖 Lore & Roleplay</div>
        </div>

        <!-- Subtab 0: SKILLS & CHECKS GRID (Collapsible Accordions by Attribute) -->
        <div *ngIf="sheetSubTab === 'skills'" class="phyrexian-card">
          <div class="skills-header-row">
            <div>
              <h3>📜 Skill Proficiencies & Check Rollers</h3>
              <p class="subtitle" style="margin-bottom: 0;">Organized by primary attribute. Expand groups or filter by proficiency.</p>
            </div>
            <label class="filter-toggle">
              <input type="checkbox" [(ngModel)]="showProficientOnly" /> Show Proficient Only (⭐)
            </label>
          </div>

          <div class="skill-accordions">
            <div *ngFor="let attr of ['STR', 'DEX', 'INT', 'WIS', 'CHA']" class="accordion-group">
              <div class="accordion-header" (click)="toggleGroup(attr)">
                <span><strong>{{ getAttributeFullName(attr) }}</strong> ({{ attr }})</span>
                <span class="accordion-arrow">{{ openGroups[attr] ? '▼' : '►' }}</span>
              </div>

              <div *ngIf="openGroups[attr]" class="accordion-body">
                <div class="skills-grid">
                  <ng-container *ngFor="let s of getSkillsByAttribute(attr)">
                    <div *ngIf="!showProficientOnly || isProficient(s.name)" class="skill-card">
                      <div class="skill-info">
                        <span class="prof-star" [class.active]="isProficient(s.name)">{{ isProficient(s.name) ? '⭐' : '⚪' }}</span>
                        <strong>{{ s.name }}</strong>
                      </div>

                      <div class="skill-actions">
                        <span class="skill-mod-badge">{{ getSkillModString(s) }}</span>
                        <button class="phyrexian-btn mini-btn" (click)="rollSkillCheck(s)">🎲 Roll</button>
                      </div>
                    </div>
                  </ng-container>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Subtab 1: Combat & Inventory -->
        <div *ngIf="sheetSubTab === 'combat'" class="tab-content">
          <div class="phyrexian-card">
            <div class="section-title-row">
              <h3>⚔️ Equipped Weapons & Attacks</h3>
              <button *ngIf="editMode" class="phyrexian-btn-secondary mini-btn" (click)="addWeapon()">+ Add Weapon</button>
            </div>

            <table class="weapons-table">
              <thead>
                <tr>
                  <th>Weapon</th>
                  <th>To Hit</th>
                  <th>Damage</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let w of char.weapons; let i = index">
                  <td>
                    <strong *ngIf="!editMode">{{ w.name }}</strong>
                    <input *ngIf="editMode" type="text" class="phyrexian-input" [(ngModel)]="w.name" (change)="saveCurrentChar()" />
                  </td>
                  <td>
                    <span *ngIf="!editMode" class="hit-badge">{{ w.attack_bonus }}</span>
                    <input *ngIf="editMode" type="text" class="phyrexian-input mini-input" [(ngModel)]="w.attack_bonus" (change)="saveCurrentChar()" />
                  </td>
                  <td>
                    <span *ngIf="!editMode">{{ w.damage_dice }} {{ w.damage_bonus }}</span>
                    <input *ngIf="editMode" type="text" class="phyrexian-input" [(ngModel)]="w.damage_dice" (change)="saveCurrentChar()" />
                  </td>
                  <td>
                    <button class="phyrexian-btn-secondary mini-btn" (click)="rollWeaponAttack(w)">🎲 Attack</button>
                    <button *ngIf="editMode" class="phyrexian-btn-secondary mini-btn delete-btn" (click)="deleteWeapon(i)">❌</button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="section-title-row" style="margin-top: 1.5rem;">
              <h3>🎒 Equipment & Gear</h3>
              <button *ngIf="editMode" class="phyrexian-btn-secondary mini-btn" (click)="addEquipment()">+ Add Item</button>
            </div>

            <div class="gear-list">
              <div class="gear-item" *ngFor="let item of char.equipment; let i = index">
                <span *ngIf="!editMode">{{ item.name }}</span>
                <input *ngIf="editMode" type="text" class="phyrexian-input" [(ngModel)]="item.name" (change)="saveCurrentChar()" />
                <span class="equipped-tag" [class.active]="item.equipped" (click)="toggleEquipped(item)">
                  {{ item.equipped ? 'Equipped' : 'Inventory' }}
                </span>
                <button *ngIf="editMode" class="phyrexian-btn-secondary mini-btn delete-btn" (click)="deleteEquipment(i)">❌</button>
              </div>
            </div>
          </div>

          <!-- Interactive Dice Panel -->
          <app-dice-roller></app-dice-roller>
        </div>

        <!-- Subtab 2: Spells & Features -->
        <div *ngIf="sheetSubTab === 'spells'" class="phyrexian-card">
          <!-- Spell Slots Tracker -->
          <div class="spell-slots-section">
            <h3>✨ Spell Slots Tracker</h3>
            <div class="slots-grid">
              <div class="slot-box" *ngFor="let lvl of [1,2,3,4,5,6,7,8,9]">
                <span class="slot-lvl">Lvl {{ lvl }}</span>
                <div class="slot-controls">
                  <button class="hp-btn" (click)="useSpellSlot(lvl)">-</button>
                  <span class="slot-val">{{ getSpellSlotUsed(lvl) }} / {{ getSpellSlotMax(lvl) }}</span>
                  <button class="hp-btn" (click)="restoreSpellSlot(lvl)">+</button>
                </div>
              </div>
            </div>
          </div>

          <h3 style="margin-top: 1.5rem;">🌟 Class Features & Racial Traits</h3>
          <div class="features-list">
            <div class="feature-card" *ngFor="let f of char.features_traits">
              <h4>{{ f.name }}</h4>
              <p>{{ f.description }}</p>
            </div>
          </div>
        </div>

        <!-- Subtab 3: Roleplay -->
        <div *ngIf="sheetSubTab === 'roleplay'" class="phyrexian-card">
          <h3>📖 Personality & Lore</h3>
          <div class="roleplay-grid">
            <div class="roleplay-box">
              <h4>Personality Traits</h4>
              <p *ngIf="!editMode">{{ char.personality_traits || 'None' }}</p>
              <textarea *ngIf="editMode" class="phyrexian-textarea" [(ngModel)]="char.personality_traits" (change)="saveCurrentChar()"></textarea>
            </div>
            <div class="roleplay-box">
              <h4>Ideals</h4>
              <p *ngIf="!editMode">{{ char.ideals || 'None' }}</p>
              <textarea *ngIf="editMode" class="phyrexian-textarea" [(ngModel)]="char.ideals" (change)="saveCurrentChar()"></textarea>
            </div>
            <div class="roleplay-box">
              <h4>Bonds</h4>
              <p *ngIf="!editMode">{{ char.bonds || 'None' }}</p>
              <textarea *ngIf="editMode" class="phyrexian-textarea" [(ngModel)]="char.bonds" (change)="saveCurrentChar()"></textarea>
            </div>
            <div class="roleplay-box">
              <h4>Flaws</h4>
              <p *ngIf="!editMode">{{ char.flaws || 'None' }}</p>
              <textarea *ngIf="editMode" class="phyrexian-textarea" [(ngModel)]="char.flaws" (change)="saveCurrentChar()"></textarea>
            </div>
          </div>

          <h3 style="margin-top: 1.5rem;">Backstory</h3>
          <p *ngIf="!editMode" class="backstory-text">{{ char.backstory || 'No backstory recorded.' }}</p>
          <textarea *ngIf="editMode" class="phyrexian-textarea" rows="4" [(ngModel)]="char.backstory" (change)="saveCurrentChar()"></textarea>
        </div>
      </ng-container>

      <ng-template #emptyState>
        <div class="phyrexian-card" style="text-align: center; padding: 4rem 2rem; max-width: 600px; margin: 2rem auto;">
          <div style="font-size: 4rem; margin-bottom: 1rem;">🗡️</div>
          <h2 style="color: var(--theme-accent); margin-bottom: 0.5rem;">No Heroes Found</h2>
          <p class="subtitle" style="margin-bottom: 2rem;">Your vault is empty. It is time to forge a new legend.</p>
          <button class="phyrexian-btn" (click)="goToForge()" style="font-size: 1.1rem; padding: 0.75rem 1.5rem;">
            ✨ Forge Your First Hero
          </button>
        </div>
      </ng-template>

      <!-- FLOATING ACTION DOCK -->
      <div *ngIf="charState.activeCharacter()" class="floating-action-dock">
        <button class="dock-btn rest-btn" (click)="openShortRestModal()" title="Short Rest">⛺ Short Rest</button>
        <button class="dock-btn rest-btn long-rest" (click)="triggerLongRest()" title="Long Rest">🌙 Long Rest</button>
        <button class="dock-btn" (click)="onLevelUp()" title="Level Up Analysis">⚡ Level Up</button>
        <button class="dock-btn" (click)="onGenerateStrategy()" title="AI Playstyle Guide">📖 AI Guide</button>
        <button class="dock-btn" (click)="onExportPdf()" title="Export PDF">📥 PDF</button>
      </div>

      <!-- LEVEL UP MODAL -->
      <div *ngIf="showLevelUpModal && levelUpAnalysis" class="modal-backdrop">
        <div class="phyrexian-card modal-card wide-modal">
          <h2>⚡ Level Up: Level {{ (charState.activeCharacter()?.char_level || 1) + 1 }}</h2>
          <p class="subtitle">Your character has reached a new level! Review the changes below.</p>

          <div class="rest-details" style="margin-bottom: 1rem;">
            <div class="rest-stat-row">
              <span>❤️ Hit Points Increase:</span>
              <strong style="color: #2ecc71;">+{{ levelUpAnalysis.hp_increase }} (Total: {{ levelUpAnalysis.new_total_hp }})</strong>
            </div>
          </div>

          <div *ngIf="levelUpAnalysis.new_features?.length > 0">
            <h3>✨ New Class Features</h3>
            <div class="gear-list" style="max-height: 200px; overflow-y: auto;">
              <div class="gear-item" *ngFor="let f of levelUpAnalysis.new_features" style="flex-direction: column; align-items: flex-start; gap: 0.25rem; padding: 0.75rem;">
                <strong>{{ f.name }}</strong>
                <span style="color: var(--text-muted); font-size: 0.85rem;">{{ f.description }}</span>
              </div>
            </div>
          </div>

          <div *ngIf="levelUpAnalysis.new_spells_known?.length > 0 || levelUpAnalysis.spell_slots_update" style="margin-top: 1rem;">
            <h3>🔮 Magical Progression</h3>
            <p *ngIf="levelUpAnalysis.spell_slots_update" style="font-size: 0.9rem; color: var(--text-muted);">
              <strong>Spell Slots Updated:</strong> (See Spells tab for full list)
            </p>
            <ul *ngIf="levelUpAnalysis.new_spells_known?.length > 0" style="font-size: 0.9rem; margin-top: 0.5rem; color: var(--text-muted);">
              <li *ngFor="let s of levelUpAnalysis.new_spells_known">Learned: <strong>{{ s }}</strong></li>
            </ul>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showLevelUpModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="applyLevelUp()">✅ Apply Level Up</button>
          </div>
        </div>
      </div>

      <!-- SHORT REST MODAL -->
      <div *ngIf="showShortRestModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h2>⛺ Short Rest & Hit Dice Healing</h2>
          <p class="subtitle">Spend Hit Dice during a 1-hour rest to recover lost Hit Points.</p>

          <div class="rest-details">
            <div class="rest-stat-row">
              <span>🎲 Hit Die Size:</span>
              <strong>d{{ getClassHitDieSize() }}</strong>
            </div>
            <div class="rest-stat-row">
              <span>⚡ CON Modifier bonus per die:</span>
              <strong>+{{ getConModifier() }}</strong>
            </div>
            <div class="rest-stat-row">
              <span>❤️ Available Hit Dice:</span>
              <strong>{{ getAvailableHitDice() }} / {{ charState.activeCharacter()?.char_level }}</strong>
            </div>
          </div>

          <div *ngIf="getAvailableHitDice() > 0" class="form-group" style="margin-top: 1rem;">
            <label>Number of Hit Dice to Spend:</label>
            <input type="number" class="phyrexian-input" [(ngModel)]="shortRestDiceToSpend" min="1" [max]="getAvailableHitDice()" />
          </div>

          <div *ngIf="getAvailableHitDice() === 0" class="warning-box">
            ⚠️ You have no available Hit Dice remaining! Take a Long Rest to recover Hit Dice.
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showShortRestModal = false">Cancel</button>
            <button *ngIf="getAvailableHitDice() > 0" class="phyrexian-btn" (click)="executeShortRest()">⛺ Spend Hit Dice & Heal</button>
          </div>
        </div>
      </div>

      <!-- JOIN CAMPAIGN MODAL -->
      <div *ngIf="showJoinModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h2>🔑 Join Campaign</h2>
          <p class="subtitle">Enter the 6-character Invite Code provided by your DM:</p>

          <div class="form-group">
            <input type="text" class="phyrexian-input uppercase-input" [(ngModel)]="joinInviteCode" placeholder="e.g. A3F9B2" style="font-size: 1.2rem; text-align: center; letter-spacing: 3px;" />
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showJoinModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="joinCampaign()">Join Realm</button>
          </div>
        </div>
      </div>

      <!-- PORTRAIT GENERATION MODAL -->
      <div *ngIf="showPortraitModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h2>🖼️ AI Portrait Generator</h2>
          <p class="subtitle">Generate a custom portrait using Pollinations.ai!</p>

          <div class="form-group">
            <label>Visual Description Prompt (Optional):</label>
            <textarea class="phyrexian-textarea" rows="3" [(ngModel)]="portraitPrompt" placeholder="e.g. Glowing golden armor, divine sword, cinematic lighting..."></textarea>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showPortraitModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="generateAiPortrait()">🎨 Generate Art</button>
          </div>
        </div>
      </div>

      <!-- STRATEGY GUIDE MODAL -->
      <div *ngIf="strategyGuideText" class="modal-backdrop">
        <div class="phyrexian-card modal-card wide-modal">
          <h2>📖 AI Strategic Playstyle Guide</h2>
          <div class="guide-content">
            <p style="white-space: pre-wrap;">{{ strategyGuideText }}</p>
          </div>
          <div class="modal-actions">
            <button class="phyrexian-btn" (click)="strategyGuideText = null">Close</button>
          </div>
        </div>
      </div>

      <!-- FULL EDIT CHARACTER SHEET MODAL -->
      <div *ngIf="showEditModal && charState.activeCharacter() as editChar" class="modal-backdrop">
        <div class="phyrexian-card modal-card wide-modal" style="max-height: 85vh; overflow-y: auto;">
          <h2>✏️ Edit Character Sheet: {{ editChar.char_name }}</h2>
          <p class="subtitle">Modify core stats, vitals, background traits, and backstory.</p>

          <div class="form-row">
            <div style="flex: 2;">
              <label>Hero Name:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="editChar.char_name" />
            </div>
            <div style="flex: 1;">
              <label>Level:</label>
              <input type="number" class="phyrexian-input" [(ngModel)]="editChar.char_level" min="1" max="20" />
            </div>
          </div>

          <div class="form-row" style="margin-top: 0.8rem;">
            <div>
              <label>Race:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="editChar.race" />
            </div>
            <div>
              <label>Class:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="editChar.char_class" />
            </div>
            <div>
              <label>Subclass:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="editChar.subclass" />
            </div>
          </div>

          <div class="form-row" style="margin-top: 0.8rem;">
            <div>
              <label>Background:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="editChar.background" />
            </div>
            <div>
              <label>Max HP:</label>
              <input type="number" class="phyrexian-input" [(ngModel)]="editChar.hp_max" />
            </div>
            <div>
              <label>Armor Class (AC):</label>
              <input type="number" class="phyrexian-input" [(ngModel)]="editChar.armor_class" />
            </div>
            <div>
              <label>Speed (ft):</label>
              <input type="number" class="phyrexian-input" [(ngModel)]="editChar.speed" />
            </div>
          </div>

          <h4 style="margin-top: 1.2rem; color: var(--theme-accent);">Ability Scores</h4>
          <div class="form-row" style="margin-top: 0.5rem;" *ngIf="editChar.stats">
            <div><label>STR:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['STR']" /></div>
            <div><label>DEX:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['DEX']" /></div>
            <div><label>CON:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['CON']" /></div>
            <div><label>INT:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['INT']" /></div>
            <div><label>WIS:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['WIS']" /></div>
            <div><label>CHA:</label><input type="number" class="phyrexian-input mini-input" [(ngModel)]="editChar.stats['CHA']" /></div>
          </div>

          <h4 style="margin-top: 1.2rem; color: var(--theme-accent);">Traits & Backstory</h4>
          <div class="form-group" style="margin-top: 0.5rem;">
            <label>Personality Traits:</label>
            <textarea class="phyrexian-textarea" rows="2" [(ngModel)]="editChar.personality_traits"></textarea>
          </div>
          <div class="form-group">
            <label>Ideals:</label>
            <textarea class="phyrexian-textarea" rows="2" [(ngModel)]="editChar.ideals"></textarea>
          </div>
          <div class="form-group">
            <label>Bonds:</label>
            <textarea class="phyrexian-textarea" rows="2" [(ngModel)]="editChar.bonds"></textarea>
          </div>
          <div class="form-group">
            <label>Flaws:</label>
            <textarea class="phyrexian-textarea" rows="2" [(ngModel)]="editChar.flaws"></textarea>
          </div>
          <div class="form-group">
            <label>Backstory:</label>
            <textarea class="phyrexian-textarea" rows="3" [(ngModel)]="editChar.backstory"></textarea>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showEditModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="saveEditModal()">💾 Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .player-container { padding-bottom: 6rem; max-width: 1200px; margin: 0 auto; }
    .vault-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .vault-selector { display: flex; align-items: center; gap: 0.75rem; }
    .vault-actions { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
    .import-label { margin: 0; cursor: pointer; }
    .rest-btn { border-color: var(--accent-gold); color: var(--accent-gold); }
    .long-rest { border-color: var(--accent-violet); color: var(--accent-violet); }
    .campaign-indicator { background: rgba(212, 175, 55, 0.15); border: 1px solid var(--accent-gold); color: var(--accent-gold); padding: 0.5rem 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.88rem; }
    .vitals-grid { display: flex; gap: 1.5rem; margin-bottom: 1.5rem; }
    .char-portrait { position: relative; cursor: pointer; }
    .portrait-img { width: 120px; height: 120px; object-fit: cover; border-radius: 8px; border: 2px solid var(--theme-accent); }
    .portrait-overlay { position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.7); font-size: 0.7rem; text-align: center; padding: 0.2rem; }
    .vitals-info { flex: 1; }
    .hero-name-row { display: flex; align-items: center; gap: 1rem; }
    .name-input { font-size: 1.4rem; font-weight: 700; max-width: 250px; }
    .edition-pill { font-size: 0.7rem; background: rgba(255, 255, 255, 0.1); padding: 0.2rem 0.5rem; border-radius: 10px; }
    .subtitle { color: var(--text-muted); margin-bottom: 1rem; }
    .edit-basics-row { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
    .vitals-boxes { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-top: 0.5rem; }
    .mini-input { width: 60px; padding: 0.2rem; text-align: center; }
    .hp-controls { display: flex; align-items: center; gap: 0.5rem; }
    .hp-btn { background: rgba(255, 255, 255, 0.1); border: 1px solid var(--border-card); color: #fff; border-radius: 4px; width: 24px; height: 24px; cursor: pointer; }
    .hp-btn:hover { background: var(--theme-accent); }
    .stats-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; margin-bottom: 1rem; }
    .stat-roll-btns { display: flex; gap: 0.25rem; margin-top: 0.4rem; justify-content: center; }
    .mini-roll-btn { font-size: 0.68rem; padding: 0.15rem 0.35rem; }
    .save-btn { border-color: var(--accent-gold); color: var(--accent-gold); }
    .roll-mode-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; padding: 0.6rem 1.25rem; }
    .roll-mode-options { display: flex; gap: 1.5rem; }
    .radio-label { font-size: 0.88rem; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; }
    .skills-header-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .filter-toggle { font-size: 0.85rem; color: var(--accent-gold); cursor: pointer; display: flex; align-items: center; gap: 0.4rem; }
    .skill-accordions { display: flex; flex-direction: column; gap: 0.75rem; }
    .accordion-group { border: 1px solid var(--border-card); border-radius: 8px; overflow: hidden; background: rgba(0,0,0,0.25); }
    .accordion-header { padding: 0.65rem 1rem; background: rgba(255,255,255,0.04); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: background 0.2s; }
    .accordion-header:hover { background: rgba(255,255,255,0.08); }
    .accordion-arrow { font-size: 0.75rem; color: var(--text-muted); }
    .accordion-body { padding: 0.75rem; }
    .skills-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
    .skill-card { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-card); border-radius: 8px; padding: 0.6rem 0.8rem; display: flex; justify-content: space-between; align-items: center; }
    .skill-info { display: flex; align-items: center; gap: 0.4rem; font-size: 0.88rem; }
    .prof-star { opacity: 0.3; }
    .prof-star.active { opacity: 1; }
    .skill-actions { display: flex; align-items: center; gap: 0.5rem; }
    .skill-mod-badge { background: rgba(255, 255, 255, 0.1); padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 700; font-size: 0.85rem; color: var(--text-gold); }
    .floating-action-dock { position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%); z-index: 999; display: flex; gap: 0.5rem; background: rgba(14, 14, 22, 0.9); backdrop-filter: blur(12px); border: 1px solid var(--border-card); padding: 0.5rem 0.8rem; border-radius: 30px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }
    .dock-btn { background: rgba(255,255,255,0.08); border: 1px solid var(--border-card); color: #fff; padding: 0.4rem 0.8rem; border-radius: 20px; font-size: 0.8rem; font-weight: 600; cursor: pointer; transition: all 0.2s; }
    .dock-btn:hover { background: var(--theme-accent); transform: translateY(-2px); }
    .slots-grid { display: grid; grid-template-columns: repeat(9, 1fr); gap: 0.5rem; margin-top: 0.75rem; }
    .slot-box { background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); padding: 0.4rem; border-radius: 6px; text-align: center; }
    .slot-lvl { font-size: 0.7rem; color: var(--text-muted); font-weight: 700; }
    .slot-controls { display: flex; align-items: center; justify-content: center; gap: 0.3rem; margin-top: 0.2rem; }
    .slot-val { font-size: 0.8rem; font-weight: 700; color: var(--accent-violet); }
    .rest-details { background: rgba(0,0,0,0.3); border: 1px solid var(--border-card); border-radius: 8px; padding: 0.75rem; }
    .rest-stat-row { display: flex; justify-content: space-between; padding: 0.3rem 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.9rem; }
    .warning-box { background: rgba(255, 75, 75, 0.15); border: 1px solid #ff4b4b; color: #ff4b4b; padding: 0.75rem; border-radius: 6px; margin-top: 1rem; font-size: 0.88rem; }
    .section-title-row { display: flex; justify-content: space-between; align-items: center; }
    .weapons-table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
    .weapons-table th, .weapons-table td { padding: 0.6rem; text-align: left; border-bottom: 1px solid var(--border-card); }
    .hit-badge { background: var(--theme-accent); color: #fff; padding: 0.2rem 0.5rem; border-radius: 4px; }
    .mini-btn { font-size: 0.75rem; padding: 0.2rem 0.5rem; }
    .delete-btn { color: #ff4b4b; border-color: #ff4b4b; margin-left: 0.3rem; }
    .gear-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; margin-top: 0.5rem; }
    .gear-item { background: rgba(0, 0, 0, 0.3); padding: 0.5rem; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; }
    .equipped-tag { font-size: 0.75rem; color: var(--text-muted); cursor: pointer; }
    .equipped-tag.active { color: var(--accent-gold); font-weight: 700; }
    .feature-card { background: rgba(0, 0, 0, 0.3); border: 1px solid var(--border-card); padding: 0.8rem; border-radius: 6px; margin-top: 0.5rem; }
    .roleplay-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; margin-bottom: 1rem; }
    .roleplay-box { background: rgba(0, 0, 0, 0.3); padding: 0.75rem; border-radius: 6px; }
    .roleplay-box h4 { font-size: 0.85rem; color: var(--text-gold); margin-bottom: 0.3rem; }
    .modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.75); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-card { width: 100%; max-width: 520px; }
    .wide-modal { max-width: 700px; max-height: 80vh; overflow-y: auto; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1.5rem; }
    .guide-content { background: rgba(0,0,0,0.4); padding: 1rem; border-radius: 8px; margin-top: 1rem; max-height: 50vh; overflow-y: auto; }

    /* ==========================================
       Player Dashboard Responsive Mobile Styles
       ========================================== */
    @media (max-width: 900px) {
      .stats-grid { grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
      .slots-grid { grid-template-columns: repeat(5, 1fr); }
    }

    @media (max-width: 768px) {
      .vault-bar { flex-direction: column; align-items: stretch; gap: 0.85rem; }
      .vault-selector { flex-direction: column; align-items: stretch; width: 100%; gap: 0.5rem; }
      .vault-actions { width: 100%; justify-content: space-between; flex-wrap: wrap; }
      .vault-actions button { flex: 1 1 45%; justify-content: center; font-size: 0.8rem; padding: 0.45rem 0.5rem; }

      .vitals-grid { flex-direction: column; align-items: center; gap: 1rem; text-align: center; }
      .char-portrait { margin: 0 auto; }
      .hero-name-row { justify-content: center; flex-wrap: wrap; }
      .name-input { text-align: center; }
      .edit-basics-row { flex-wrap: wrap; justify-content: center; }
      .edit-basics-row input { flex: 1 1 45%; }
      .vitals-boxes { grid-template-columns: repeat(2, 1fr); width: 100%; }

      .skills-grid { grid-template-columns: 1fr; }
      .slots-grid { grid-template-columns: repeat(3, 1fr); }
      .gear-list { grid-template-columns: 1fr; }
      .roleplay-grid { grid-template-columns: 1fr; }

      .roll-mode-bar { flex-direction: column; gap: 0.6rem; align-items: flex-start; }
      .roll-mode-options { flex-wrap: wrap; gap: 0.75rem; }

      .floating-action-dock {
        left: 50%;
        transform: translateX(-50%);
        bottom: 0.75rem;
        width: 95vw;
        overflow-x: auto;
        white-space: nowrap;
        justify-content: flex-start;
        border-radius: 18px;
        padding: 0.4rem 0.6rem;
      }
      .dock-btn { flex-shrink: 0; font-size: 0.75rem; padding: 0.35rem 0.65rem; }
    }

    @media (max-width: 500px) {
      .stats-grid { grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
      .vitals-boxes { grid-template-columns: 1fr; }
    }
  `]
})
export class PlayerComponent implements OnInit, OnDestroy {
  activeTab: 'sheet' = 'sheet';
  sheetSubTab: 'skills' | 'combat' | 'spells' | 'roleplay' = 'skills';
  editMode = false;
  showEditModal = false;
  showPortraitModal = false;
  showJoinModal = false;
  showShortRestModal = false;
  showProficientOnly = false;
  showLevelUpModal = false;
  levelUpAnalysis: any = null;
  shortRestDiceToSpend = 1;
  joinInviteCode = '';
  rollMode: 'normal' | 'advantage' | 'disadvantage' = 'normal';

  portraitPrompt = '';
  strategyGuideText: string | null = null;

  openGroups: { [key: string]: boolean } = {
    STR: true,
    DEX: true,
    INT: false,
    WIS: false,
    CHA: false
  };

  allSkills: SkillDefinition[] = [
    { name: 'Athletics', ability: 'STR' },
    { name: 'Acrobatics', ability: 'DEX' },
    { name: 'Sleight of Hand', ability: 'DEX' },
    { name: 'Stealth', ability: 'DEX' },
    { name: 'Arcana', ability: 'INT' },
    { name: 'History', ability: 'INT' },
    { name: 'Investigation', ability: 'INT' },
    { name: 'Nature', ability: 'INT' },
    { name: 'Religion', ability: 'INT' },
    { name: 'Animal Handling', ability: 'WIS' },
    { name: 'Insight', ability: 'WIS' },
    { name: 'Medicine', ability: 'WIS' },
    { name: 'Perception', ability: 'WIS' },
    { name: 'Survival', ability: 'WIS' },
    { name: 'Deception', ability: 'CHA' },
    { name: 'Intimidation', ability: 'CHA' },
    { name: 'Performance', ability: 'CHA' },
    { name: 'Persuasion', ability: 'CHA' },
  ];

  private wsSub: Subscription | null = null;

  constructor(
    public charState: CharacterStateService,
    private rollToast: RollToastService,
    private http: HttpClient,
    private router: Router,
    private wsService: WebSocketService
  ) {
    effect(() => {
      const char = this.charState.activeCharacter();
      if (char && char.active_campaign) {
        this.wsService.connect(char.active_campaign);
      } else {
        this.wsService.disconnect();
      }
    });
  }

  ngOnInit() {
    this.charState.loadCharacters().subscribe();

    this.wsSub = this.wsService.messages$.subscribe((msg: WsMessage) => {
      const char = this.charState.activeCharacter();
      if (!char) return;

      if (msg.type === 'roll_request') {
        const req = msg['payload'];
        // Check if this request is for the active character
        const charId = req.char_filename.replace('.json', '').split('_').pop();
        if (char.char_id === charId || req.char_name === char.char_name) {
          const secText = req.is_secret ? '🔒 SECRET' : 'DM';
          const title = `⚠️ ${secText} ROLL REQUESTED`;
          const details = `The DM has requested a ${req.roll_type} (${req.stat}) check!\nReason: ${req.reason}`;
          this.rollToast.showMessage(title, details);

          // Execute the roll automatically (or we could open a modal, but auto-rolling is faster)
          this.executeRollRequest(req.roll_type, req.stat);
        }
      } else if (msg.type === 'whisper') {
        const whisper = msg['payload'];
        if (whisper.recipient === char.char_name || whisper.recipient === 'All') {
          this.rollToast.showMessage(`💬 WHISPER FROM ${whisper.sender}`, whisper.message);
        }
      }
    });
  }

  ngOnDestroy() {
    if (this.wsSub) {
      this.wsSub.unsubscribe();
    }
  }

  toggleGroup(attr: string) {
    this.openGroups[attr] = !this.openGroups[attr];
  }

  getSkillsByAttribute(attr: string): SkillDefinition[] {
    return this.allSkills.filter((s) => s.ability === attr);
  }

  getAttributeFullName(attr: string): string {
    const names: { [key: string]: string } = {
      STR: 'Strength',
      DEX: 'Dexterity',
      INT: 'Intelligence',
      WIS: 'Wisdom',
      CHA: 'Charisma'
    };
    return names[attr] || attr;
  }

  goToForge() {
    this.router.navigate(['/forge']);
  }

  getClassHitDieSize(): number {
    const char = this.charState.activeCharacter();
    const c = (char?.char_class || '').toLowerCase();
    if (c.includes('barbarian')) return 12;
    if (c.includes('fighter') || c.includes('paladin') || c.includes('ranger')) return 10;
    if (c.includes('sorcerer') || c.includes('wizard')) return 6;
    return 8; // Bard, Cleric, Druid, Monk, Rogue, Warlock
  }

  getConModifier(): number {
    const char = this.charState.activeCharacter();
    const conVal = char?.stats?.['CON'] || 10;
    return Math.floor((conVal - 10) / 2);
  }

  getAvailableHitDice(): number {
    const char = this.charState.activeCharacter();
    if (!char) return 0;
    const total = char.char_level || 1;
    const used = char.hit_dice_used || 0;
    return Math.max(0, total - used);
  }

  openShortRestModal() {
    this.shortRestDiceToSpend = 1;
    this.showShortRestModal = true;
  }

  executeShortRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const available = this.getAvailableHitDice();
    if (available <= 0) return;

    const count = Math.min(available, Math.max(1, this.shortRestDiceToSpend));
    const dieSize = this.getClassHitDieSize();
    const conMod = this.getConModifier();

    let rollSum = 0;
    const rolls: number[] = [];
    for (let i = 0; i < count; i++) {
      const r = Math.floor(Math.random() * dieSize) + 1;
      rolls.push(r);
      rollSum += r;
    }
    const conBonus = conMod * count;
    const totalHealed = Math.max(0, rollSum + conBonus);

    const oldHp = char.hp_current ?? char.hp_max;
    const newHp = Math.min(char.hp_max, oldHp + totalHealed);

    char.hp_current = newHp;
    char.hit_dice_used = (char.hit_dice_used || 0) + count;

    if (char.char_class.toLowerCase().includes('warlock') && char.spell_slots) {
      Object.keys(char.spell_slots).forEach((key) => {
        if (char.spell_slots) char.spell_slots[key].used = 0;
      });
    }

    this.saveCurrentChar();
    this.showShortRestModal = false;

    this.rollToast.showRoll({
      title: `⛺ SHORT REST HEAL (${count}d${dieSize})`,
      expression: `${count}d${dieSize} (${rolls.join(', ')}) ${conBonus >= 0 ? '+' + conBonus : conBonus}`,
      raw: rolls[0],
      modifier: conBonus,
      total: totalHealed,
      message: `Healed for +${totalHealed} HP! (${oldHp} ➡️ ${newHp})`
    });
  }

  triggerLongRest() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    char.hp_current = char.hp_max;

    const totalHd = char.char_level || 1;
    const currentUsed = char.hit_dice_used || 0;
    const recoverCount = Math.floor(totalHd / 2) || 1;
    char.hit_dice_used = Math.max(0, currentUsed - recoverCount);

    if (char.spell_slots) {
      Object.keys(char.spell_slots).forEach((key) => {
        if (char.spell_slots) char.spell_slots[key].used = 0;
      });
    }
    this.saveCurrentChar();
    this.rollToast.showMessage('🌙 LONG REST COMPLETED', `Full HP, spell slots, and ${recoverCount} Hit Dice restored for ${char.char_name}.`);
  }

  getSpellSlotMax(lvl: number): number {
    const char = this.charState.activeCharacter();
    return char?.spell_slots?.[`level_${lvl}`]?.max || 0;
  }

  getSpellSlotUsed(lvl: number): number {
    const char = this.charState.activeCharacter();
    return char?.spell_slots?.[`level_${lvl}`]?.used || 0;
  }

  useSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.spell_slots) char.spell_slots = {};
    const key = `level_${lvl}`;
    if (!char.spell_slots[key]) char.spell_slots[key] = { max: 4, used: 0 };
    char.spell_slots[key].used = Math.min(char.spell_slots[key].max, char.spell_slots[key].used + 1);
    this.saveCurrentChar();
  }

  restoreSpellSlot(lvl: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.spell_slots) return;
    const key = `level_${lvl}`;
    if (char.spell_slots[key]) {
      char.spell_slots[key].used = Math.max(0, char.spell_slots[key].used - 1);
      this.saveCurrentChar();
    }
  }

  isProficient(skillName: string): boolean {
    const char = this.charState.activeCharacter();
    return char?.skill_proficiencies?.includes(skillName) || false;
  }

  getSkillModifier(skill: SkillDefinition): number {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return 0;
    const statVal = char.stats[skill.ability] || 10;
    const statMod = Math.floor((statVal - 10) / 2);
    const profBonus = char.proficiency_bonus || 2;
    const isProf = this.isProficient(skill.name);
    return statMod + (isProf ? profBonus : 0);
  }

  getSkillModString(skill: SkillDefinition): string {
    const mod = this.getSkillModifier(skill);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }

  rollD20(): number {
    if (this.rollMode === 'advantage') {
      const r1 = Math.floor(Math.random() * 20) + 1;
      const r2 = Math.floor(Math.random() * 20) + 1;
      return Math.max(r1, r2);
    } else if (this.rollMode === 'disadvantage') {
      const r1 = Math.floor(Math.random() * 20) + 1;
      const r2 = Math.floor(Math.random() * 20) + 1;
      return Math.min(r1, r2);
    }
    return Math.floor(Math.random() * 20) + 1;
  }

  rollSkillCheck(skill: SkillDefinition) {
    const raw = this.rollD20();
    const mod = this.getSkillModifier(skill);
    const total = raw + mod;
    const modeLabel = this.rollMode !== 'normal' ? ` (${this.rollMode.toUpperCase()})` : '';
    const expr = `1d20 (${raw}) ${mod >= 0 ? '+' + mod : mod}`;

    this.rollToast.showRoll({
      title: `🎲 ${skill.name.toUpperCase()} CHECK${modeLabel}`,
      expression: expr,
      raw,
      modifier: mod,
      total,
      mode: this.rollMode
    });
  }

  rollAbilityCheck(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const raw = this.rollD20();
    const total = raw + mod;
    const modeLabel = this.rollMode !== 'normal' ? ` (${this.rollMode.toUpperCase()})` : '';
    const expr = `1d20 (${raw}) ${mod >= 0 ? '+' + mod : mod}`;

    this.rollToast.showRoll({
      title: `🎲 ${stat} CHECK${modeLabel}`,
      expression: expr,
      raw,
      modifier: mod,
      total,
      mode: this.rollMode
    });
  }

  rollSavingThrow(stat: string) {
    const char = this.charState.activeCharacter();
    if (!char || !char.stats) return;
    const val = char.stats[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const isSaveProf = char.saving_throws?.includes(stat);
    const profBonus = char.proficiency_bonus || 2;
    const totalMod = mod + (isSaveProf ? profBonus : 0);
    const raw = this.rollD20();
    const total = raw + totalMod;
    const modeLabel = this.rollMode !== 'normal' ? ` (${this.rollMode.toUpperCase()})` : '';
    const expr = `1d20 (${raw}) ${totalMod >= 0 ? '+' + totalMod : totalMod}`;

    this.rollToast.showRoll({
      title: `🛡️ ${stat} SAVING THROW${modeLabel}`,
      expression: expr,
      raw,
      modifier: totalMod,
      total,
      mode: this.rollMode
    });
  }

  executeRollRequest(rollType: string, stat: string) {
    if (rollType.toLowerCase() === 'save') {
      this.rollSavingThrow(stat);
    } else if (rollType.toLowerCase() === 'skill') {
      const skill = this.allSkills.find(s => s.name.toLowerCase() === stat.toLowerCase());
      if (skill) this.rollSkillCheck(skill);
      else this.rollAbilityCheck(stat);
    } else {
      this.rollAbilityCheck(stat);
    }
  }

  joinCampaign() {
    const char = this.charState.activeCharacter();
    if (!char || !this.joinInviteCode) return;

    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/join`, {
      invite_code: this.joinInviteCode.toUpperCase(),
      char_filename: `${char.char_name.toLowerCase()}_${char.char_id}.json`
    }).subscribe({
      next: (res) => {
        this.showJoinModal = false;
        char.active_campaign = res.campaign_name;
        this.saveCurrentChar();
        this.rollToast.showMessage('🏰 CAMPAIGN JOINED', `Joined campaign "${res.campaign_name}" successfully!`);
      },
      error: (err) => this.rollToast.showMessage('⚠️ JOIN FAILED', err.error?.detail || 'Failed to join campaign.')
    });
  }

  onSelectCharacter(charId: string) {
    const selected = this.charState.characters().find((c) => c.char_id === charId);
    if (selected) {
      this.charState.activeCharacter.set(selected);
    }
  }

  openEditModal() {
    this.showEditModal = true;
  }

  saveEditModal() {
    this.showEditModal = false;
    this.saveCurrentChar(true);
  }

  toggleEditMode() {
    this.editMode = !this.editMode;
    if (!this.editMode) {
      this.saveCurrentChar(true);
    }
  }

  saveCurrentChar(showToast = false) {
    const char = this.charState.activeCharacter();
    if (!char) return;

    const copy = { ...char };
    this.charState.activeCharacter.set(copy);

    if (copy.char_id && copy.char_id !== 'default_paladin') {
      this.charState.updateCharacter(copy.char_id, copy).subscribe({
        next: (updated) => {
          if (updated) {
            this.charState.activeCharacter.set(updated);
            this.updateLocalCharactersList(updated);
          }
          if (showToast) {
            this.rollToast.showMessage('💾 SHEET SAVED', `Saved changes for ${copy.char_name}.`);
          }
        },
        error: () => {
          this.charState.saveCharacter(copy).subscribe({
            next: (saved) => {
              if (saved) {
                this.charState.activeCharacter.set(saved);
                this.updateLocalCharactersList(saved);
              }
              if (showToast) {
                this.rollToast.showMessage('💾 SHEET SAVED', `Saved ${copy.char_name} to vault.`);
              }
            }
          });
        }
      });
    } else {
      this.charState.saveCharacter(copy).subscribe({
        next: (saved) => {
          if (saved) {
            this.charState.activeCharacter.set(saved);
            this.updateLocalCharactersList(saved);
          }
          if (showToast) {
            this.rollToast.showMessage('💾 HERO FORGED', `Saved ${copy.char_name} to vault.`);
          }
        }
      });
    }
  }

  private updateLocalCharactersList(char: CharacterSchema) {
    const currentList = this.charState.characters();
    const idx = currentList.findIndex((c) => c.char_id === char.char_id);
    if (idx >= 0) {
      const newList = [...currentList];
      newList[idx] = char;
      this.charState.characters.set(newList);
    } else {
      this.charState.characters.set([...currentList, char]);
    }
  }

  adjustHp(delta: number) {
    const char = this.charState.activeCharacter();
    if (!char) return;
    const current = char.hp_current ?? char.hp_max;
    const updatedHp = Math.max(0, Math.min(char.hp_max, current + delta));
    const updated = { ...char, hp_current: updatedHp };
    this.charState.activeCharacter.set(updated);
    if (char.char_id) {
      this.charState.updateCharacter(char.char_id, updated).subscribe();
    }
  }

  addWeapon() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.weapons) char.weapons = [];
    char.weapons.push({ name: 'New Weapon', attack_bonus: '+5', damage_dice: '1d8+3' });
    this.saveCurrentChar();
  }

  deleteWeapon(index: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.weapons) return;
    char.weapons.splice(index, 1);
    this.saveCurrentChar();
  }

  addEquipment() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    if (!char.equipment) char.equipment = [];
    char.equipment.push({ name: 'New Item', equipped: false });
    this.saveCurrentChar();
  }

  deleteEquipment(index: number) {
    const char = this.charState.activeCharacter();
    if (!char || !char.equipment) return;
    char.equipment.splice(index, 1);
    this.saveCurrentChar();
  }

  toggleEquipped(item: EquipmentItem) {
    item.equipped = !item.equipped;
    this.saveCurrentChar();
  }

  getPortraitUrl(char: any): string {
    if (char && char.char_portrait && !char.char_portrait.includes('anvil.png')) {
      return char.char_portrait;
    }
    const className = (char?.char_class || '').toLowerCase();
    if (className.includes('paladin') || className.includes('fighter') || className.includes('barbarian')) {
      return 'https://image.pollinations.ai/prompt/sir%20valeros%20dnd%20paladin%20knight%20in%20shining%20armor%20cinematic%20portrait?width=300&height=300&nologo=true';
    } else if (className.includes('wizard') || className.includes('sorcerer') || className.includes('warlock') || className.includes('mage')) {
      return 'https://image.pollinations.ai/prompt/epic%20dnd%20wizard%20archmage%20glowing%20runes%20cinematic%20portrait?width=300&height=300&nologo=true';
    } else if (className.includes('rogue') || className.includes('ranger') || className.includes('monk')) {
      return 'https://image.pollinations.ai/prompt/epic%20dnd%20shadow%20rogue%20assassin%20hooded%20cinematic%20portrait?width=300&height=300&nologo=true';
    }
    return 'https://image.pollinations.ai/prompt/epic%20dnd%20heroic%20paladin%20knight%20in%20shining%20armor%20cinematic%20portrait?width=300&height=300&nologo=true';
  }

  generateAiPortrait() {
    const char = this.charState.activeCharacter();
    if (!char || !char.char_id) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/portrait`, {
      char_id: char.char_id,
      prompt: this.portraitPrompt
    }).subscribe((res) => {
      this.showPortraitModal = false;
      if (res.portrait_url) {
        char.char_portrait = res.portrait_url;
        this.saveCurrentChar();
      }
    });
  }

  onLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/level-up-analysis`, {
      character: char
    }).subscribe((analysis) => {
      this.levelUpAnalysis = analysis;
      this.showLevelUpModal = true;
    });
  }

  applyLevelUp() {
    const char = this.charState.activeCharacter();
    if (!char || !this.levelUpAnalysis) return;

    // Apply basic stat changes
    char.char_level = (char.char_level || 1) + 1;
    char.hp_max = this.levelUpAnalysis.new_total_hp;
    char.hp_current = char.hp_max;

    // Apply new features
    if (this.levelUpAnalysis.new_features) {
      if (!char.features_traits) char.features_traits = [];
      char.features_traits = [...char.features_traits, ...this.levelUpAnalysis.new_features];
    }

    // Save back to API
    this.http.put<CharacterSchema>(`${environment.apiBaseUrl}/characters/${char.char_id}`, char)
      .subscribe({
        next: (updatedChar) => {
          this.charState.saveCharacter(updatedChar).subscribe();
          this.showLevelUpModal = false;
          this.levelUpAnalysis = null;
          this.rollToast.showMessage(`⚡ LEVEL UP: ${char.char_name}`, `Successfully leveled up to ${char.char_level}!`);
        },
        error: () => this.rollToast.showMessage('⚠️ LEVEL UP FAILED', 'Failed to save leveled up character.')
      });
  }

  onGenerateStrategy() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>(`${environment.apiBaseUrl}/forge/playstyle-guide`, char).subscribe((res) => {
      this.strategyGuideText = res.guide_markdown;
    });
  }

  onExportPdf() {
    const char = this.charState.activeCharacter();
    if (!char || !char.char_id) return;
    this.rollToast.showMessage('📄 EXPORTING PDF', 'Generating your character sheet...');
    this.http.post(`${environment.apiBaseUrl}/characters/${char.char_id}/export-pdf`, {}, { responseType: 'blob' })
      .subscribe({
        next: (blob) => {
          const url = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `${char.char_name.replace(/ /g, '_').toLowerCase()}_sheet.pdf`;
          document.body.appendChild(a);
          a.click();
          window.URL.revokeObjectURL(url);
          a.remove();
        },
        error: () => this.rollToast.showMessage('⚠️ EXPORT FAILED', 'Failed to generate character sheet.')
      });
  }

  onImportPdf(event: any) {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    this.http.post<CharacterSchema>(`${environment.apiBaseUrl}/characters/import-pdf`, formData).subscribe({
      next: (imported) => {
        this.charState.saveCharacter(imported).subscribe();
        this.rollToast.showMessage('📥 PDF IMPORTED', `Successfully imported ${imported.char_name}!`);
      },
      error: () => this.rollToast.showMessage('⚠️ IMPORT FAILED', 'Failed to import PDF character sheet.')
    });
  }

  rollWeaponAttack(w: Weapon) {
    const raw = this.rollD20();
    const modNum = parseInt(w.attack_bonus) || 0;
    const total = raw + modNum;
    const modeLabel = this.rollMode !== 'normal' ? ` (${this.rollMode.toUpperCase()})` : '';
    const expr = `1d20 (${raw}) ${w.attack_bonus}`;

    this.rollToast.showRoll({
      title: `⚔️ ${w.name.toUpperCase()} ATTACK${modeLabel}`,
      expression: expr,
      raw,
      modifier: modNum,
      total,
      mode: this.rollMode
    });
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
