import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { RollToastService } from '../../core/services/roll-toast.service';
import { CharacterStateService } from '../../core/services/character-state.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { environment } from '../../../environments/environment';

export interface PartyMember {
  char_id?: string;
  name: string;
  char_class: string;
  level: number;
  hp_current: number;
  hp_max: number;
  ac: number;
  passive_perception: number;
  conditions: string[];
  stats?: { [key: string]: number };
  portrait?: string;
}

export interface InitiativeCombatant {
  id: string;
  name: string;
  initiative: number;
  hp: number;
  max_hp: number;
  ac: number;
  dex: number;
  is_player: boolean;
  portrait?: string;
  statblock?: string;
}

@Component({
  selector: 'app-dm',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="dm-container">
      <!-- Top Campaign Header -->
      <div class="phyrexian-card campaign-header">
        <div class="campaign-info">
          <div class="campaign-selector-row">
            <h2>🏰 DM Workspace:</h2>
            <select class="phyrexian-select campaign-select" [(ngModel)]="campaignName" (change)="onCampaignSelect()">
              <option *ngFor="let c of userCampaigns" [value]="c.campaign_name">{{ c.campaign_name }}</option>
              <option *ngIf="userCampaigns.length === 0" [value]="campaignName">{{ campaignName }}</option>
            </select>
            <button class="phyrexian-btn-secondary mini-btn" (click)="showNewCampaignModal = true">➕ New Campaign</button>
          </div>
          <span class="invite-badge" *ngIf="inviteCode">Invite Code: <strong>{{ inviteCode }}</strong></span>
        </div>
        <div class="campaign-actions">
          <button class="phyrexian-btn-secondary" (click)="generateInviteCode()">🔑 Generate Invite Code</button>
          <button class="phyrexian-btn" (click)="showWhisperModal = true">💬 Send Whisper</button>
        </div>
      </div>

      <!-- DM Navigation Tabs -->
      <div class="nav-tabs">
        <div class="tab-item" [class.active]="activeTab === 'notes'" (click)="activeTab = 'notes'">📝 Campaign Notes</div>
        <div class="tab-item" [class.active]="activeTab === 'party'" (click)="activeTab = 'party'">👥 Live Party Tracker</div>
        <div class="tab-item" [class.active]="activeTab === 'initiative'" (click)="activeTab = 'initiative'">⚔️ Initiative Tracker</div>
        <div class="tab-item" [class.active]="activeTab === 'generators'" (click)="activeTab = 'generators'">🎲 AI Generators</div>
        <div class="tab-item" [class.active]="activeTab === 'prep'" (click)="activeTab = 'prep'">📜 Session Prep</div>
      </div>

      <!-- TAB 0: CAMPAIGN NOTES -->
      <div *ngIf="activeTab === 'notes'" class="phyrexian-card">
        <h3>📝 Campaign Lore & DM Notes</h3>
        <p class="subtitle">Record plot points, secret quest hooks, and session notes. Auto-saves to workspace.</p>

        <textarea
          class="phyrexian-textarea"
          rows="12"
          [(ngModel)]="campaignNotes"
          placeholder="e.g. Chapter 3: The heroes enter the Sunless Citadel..."
          (change)="saveCampaignNotes()">
        </textarea>
      </div>

      <!-- TAB 1: PARTY TRACKER -->
      <div *ngIf="activeTab === 'party'" class="phyrexian-card">
        <div class="section-header">
          <h3>👥 Active Party Roster</h3>
          <div class="party-header-btns">
            <button class="phyrexian-btn-secondary" (click)="showAddMemberModal = true">➕ Add Member</button>
            <button class="phyrexian-btn" (click)="showRollModal = true">🎲 Issue Roll Request</button>
          </div>
        </div>
        <p class="subtitle">Monitor health, status conditions, passive perception, and roll quick ability checks.</p>

        <div *ngIf="partyMembers.length === 0" class="empty-party-card">
          <p>🛡️ No active hero characters in <strong>{{ campaignName }}</strong> yet.</p>
          <button class="phyrexian-btn" (click)="showAddMemberModal = true">➕ Add First Party Member</button>
        </div>

        <div class="party-grid">
          <div class="party-card" *ngFor="let m of partyMembers">
            <div class="card-header">
              <div class="member-title">
                <img [src]="m.portrait || 'https://img.icons8.com/color/96/knight.png'" class="mini-portrait" />
                <div>
                  <h4>{{ m.name }}</h4>
                  <span class="class-tag">Lvl {{ m.level }} {{ m.char_class }}</span>
                </div>
              </div>
            </div>

            <div class="vitals-row">
              <span>🛡️ AC: {{ m.ac }}</span>
              <span>👁️ Perception: {{ m.passive_perception }}</span>
            </div>

            <div class="hp-row">
              <label>HP:</label>
              <button class="hp-btn" (click)="adjustHp(m, -1)">-</button>
              <input type="number" class="phyrexian-input mini-hp-input" [(ngModel)]="m.hp_current" min="0" [max]="m.hp_max" />
              <span>/ {{ m.hp_max }}</span>
              <button class="hp-btn" (click)="adjustHp(m, 1)">+</button>
            </div>

            <!-- DM Quick Roll Stats -->
            <div class="stat-rolls-section">
              <span class="section-sublabel">DM Quick Check:</span>
              <div class="mini-stat-grid">
                <button *ngFor="let st of ['STR','DEX','CON','INT','WIS','CHA']" class="phyrexian-btn-secondary mini-stat-btn" (click)="quickDmStatRoll(m, st)">
                  {{ st }}
                </button>
              </div>
            </div>

            <!-- Status Badges -->
            <div class="conditions-row">
              <span
                *ngFor="let cond of availableConditions"
                class="cond-badge"
                [class.active]="m.conditions.includes(cond)"
                (click)="toggleCondition(m, cond)">
                {{ cond }}
              </span>
            </div>

            <button class="phyrexian-btn-secondary full-btn mini-btn" style="margin-top: 0.75rem;" (click)="openSingleRollModal(m)">
              🎲 Private Roll Request
            </button>
          </div>
        </div>
      </div>

      <!-- TAB 2: INITIATIVE TRACKER -->
      <div *ngIf="activeTab === 'initiative'" class="phyrexian-card">
        <div class="init-header">
          <h3>⚔️ Initiative Combat Tracker</h3>
          <div class="init-actions">
            <button class="phyrexian-btn-secondary" (click)="importPartyToInitiative()">👥 Import Party</button>
            <button class="phyrexian-btn-secondary" (click)="rollAllInitiative()">🎲 Roll All</button>
            <button class="phyrexian-btn" (click)="nextTurn()">Next Turn ➡️</button>
          </div>
        </div>

        <div class="add-combatant-row">
          <input type="text" class="phyrexian-input" placeholder="Combatant Name (e.g. Goblin Warlord)" [(ngModel)]="newCombatantName" />
          <input type="number" class="phyrexian-input" placeholder="Init Score" [(ngModel)]="newCombatantInit" style="width: 100px;" />
          <input type="number" class="phyrexian-input" placeholder="HP" [(ngModel)]="newCombatantHp" style="width: 90px;" />
          <button class="phyrexian-btn" (click)="addCombatant()">+ Add Monster</button>
        </div>

        <table class="init-table" *ngIf="combatants.length > 0">
          <thead>
            <tr>
              <th>Turn</th>
              <th>Combatant</th>
              <th>Initiative</th>
              <th>HP</th>
              <th>Actions & Info</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let c of combatants; let i = index" [class.active-turn]="i === activeTurnIndex">
              <td><span *ngIf="i === activeTurnIndex" class="turn-indicator">⚔️ CURRENT</span></td>
              <td>
                <div class="combatant-name-cell">
                  <img [src]="c.portrait || 'https://img.icons8.com/color/96/monster.png'" class="mini-portrait" />
                  <strong>{{ c.name }}</strong>
                </div>
              </td>
              <td>{{ c.initiative }}</td>
              <td>
                <div class="hp-cell">
                  <input type="number" class="phyrexian-input mini-hp-input" [(ngModel)]="c.hp" />
                  <span>/ {{ c.max_hp }}</span>
                </div>
              </td>
              <td>
                <div class="action-cell-btns">
                  <button class="phyrexian-btn-secondary mini-btn" (click)="openStatblock(c)">📜 Statblock</button>
                  <button class="clear-btn" (click)="removeCombatant(i)">❌ Remove</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- TAB 3: AI GENERATORS -->
      <div *ngIf="activeTab === 'generators'" class="phyrexian-card">
        <h3>🎲 AI Encounter & NPC Generators</h3>

        <div class="generator-section">
          <h4>⚔️ Random Encounter Generator</h4>
          <div class="form-row">
            <input type="number" class="phyrexian-input" [(ngModel)]="avgLevel" placeholder="Avg Level" />
            <input type="text" class="phyrexian-input" [(ngModel)]="location" placeholder="Environment (e.g. Dungeon)" />
            <button class="phyrexian-btn" (click)="generateEncounter()">Generate Encounter</button>
          </div>
          <div *ngIf="encounterResult" class="result-box">
            <p><strong>Encounter Text:</strong> {{ encounterResult.encounter_text }}</p>
          </div>
        </div>

        <div class="generator-section" style="margin-top: 2rem;">
          <h4>👤 Quick NPC Forge</h4>
          <div class="form-row">
            <input type="text" class="phyrexian-input" [(ngModel)]="npcConcept" placeholder="NPC Concept (e.g. Greedy merchant thief)" />
            <button class="phyrexian-btn" (click)="generateNpc()">Forge NPC</button>
          </div>
          <div *ngIf="npcResult" class="result-box">
            <p style="white-space: pre-wrap;">{{ npcResult }}</p>
          </div>
        </div>
      </div>

      <!-- TAB 4: SESSION PREP -->
      <div *ngIf="activeTab === 'prep'" class="phyrexian-card">
        <h3>📜 AI Session Prep Assistant</h3>
        <p class="subtitle">Enter your recap and ideas to generate structured DM session notes.</p>

        <div class="form-group">
          <label>Campaign Recap & DM Ideas:</label>
          <textarea class="phyrexian-textarea" rows="4" [(ngModel)]="prepNotes" placeholder="Recap: The party defeated the goblin warlord... Ideas: Introduce a secretive cult next."></textarea>
        </div>
        <button class="phyrexian-btn" (click)="generatePrep()">Generate Session Prep</button>

        <div *ngIf="prepResult" class="result-box">
          <p style="white-space: pre-wrap;">{{ prepResult }}</p>
        </div>
      </div>

      <!-- WHISPER MODAL -->
      <div *ngIf="showWhisperModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h3>💬 Secret Whisper Chat</h3>
          <div class="form-group">
            <label>Recipient:</label>
            <select class="phyrexian-select" [(ngModel)]="whisperRecipient">
              <option value="All">All Players</option>
              <option *ngFor="let m of partyMembers" [value]="m.name">{{ m.name }}</option>
            </select>
          </div>

          <div class="form-group">
            <label>Message:</label>
            <textarea class="phyrexian-textarea" rows="3" [(ngModel)]="whisperMessage"></textarea>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showWhisperModal = false">Close</button>
            <button class="phyrexian-btn" (click)="sendWhisper()">Send Whisper</button>
          </div>
        </div>
      </div>

      <!-- ROLL REQUEST MODAL -->
      <div *ngIf="showRollModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h3>🎲 Issue Private Roll Request</h3>

          <div class="form-group">
            <label>Target Member:</label>
            <select class="phyrexian-select" [(ngModel)]="rollTargetMember">
              <option *ngFor="let m of partyMembers" [value]="m.name">{{ m.name }}</option>
            </select>
          </div>

          <div class="form-row">
            <div>
              <label>Roll Type:</label>
              <select class="phyrexian-select" [(ngModel)]="rollType">
                <option value="ability_check">Ability Check</option>
                <option value="saving_throw">Saving Throw</option>
                <option value="attack_roll">Attack Roll</option>
              </select>
            </div>
            <div>
              <label>Stat:</label>
              <select class="phyrexian-select" [(ngModel)]="rollStat">
                <option value="STR">STR</option>
                <option value="DEX">DEX</option>
                <option value="CON">CON</option>
                <option value="INT">INT</option>
                <option value="WIS">WIS</option>
                <option value="CHA">CHA</option>
              </select>
            </div>
          </div>

          <div class="form-group" style="margin-top: 1rem;">
            <label>Reason / Context:</label>
            <input type="text" class="phyrexian-input" [(ngModel)]="rollReason" placeholder="e.g. Dragon Breath Fire Save" />
          </div>

          <div class="form-group">
            <label class="secret-checkbox">
              <input type="checkbox" [(ngModel)]="isSecretRoll" /> 🔒 Secret Roll (Hide result from player)
            </label>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showRollModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="sendRollRequest()">Request Roll</button>
          </div>
        </div>
      </div>

      <!-- STATBLOCK MODAL -->
      <div *ngIf="selectedStatblockCombatant" class="modal-backdrop">
        <div class="phyrexian-card modal-card wide-modal">
          <h2>📜 Statblock: {{ selectedStatblockCombatant.name }}</h2>
          <p class="subtitle">AC: {{ selectedStatblockCombatant.ac }} | HP: {{ selectedStatblockCombatant.max_hp }} | DEX: {{ selectedStatblockCombatant.dex }}</p>

          <div class="statblock-content">
            <p>{{ selectedStatblockCombatant.statblock || 'Standard D&D 5e monster statblock.' }}</p>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="openBeyondUrl(selectedStatblockCombatant.name)">🌐 View on D&D Beyond</button>
            <button class="phyrexian-btn" (click)="selectedStatblockCombatant = null">Close</button>
          </div>
        </div>
      </div>

      <!-- CREATE NEW CAMPAIGN MODAL -->
      <div *ngIf="showNewCampaignModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h3>🏰 Create New Campaign</h3>
          <p class="subtitle">Establish a new campaign realm for your party.</p>

          <div class="form-group">
            <label>Campaign Name:</label>
            <input type="text" class="phyrexian-input" [(ngModel)]="newCampaignTitle" placeholder="e.g. Curse of Strahd" />
          </div>

          <div class="form-group">
            <label>Initial DM Notes (Optional):</label>
            <textarea class="phyrexian-textarea" rows="3" [(ngModel)]="newCampaignNotes" placeholder="Campaign setting and starting plot points..."></textarea>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showNewCampaignModal = false">Cancel</button>
            <button class="phyrexian-btn" (click)="createNewCampaign()">Create Campaign</button>
          </div>
        </div>
      </div>

      <!-- ADD PARTY MEMBER MODAL -->
      <div *ngIf="showAddMemberModal" class="modal-backdrop">
        <div class="phyrexian-card modal-card">
          <h3>👤 Add Hero to {{ campaignName }}</h3>
          <p class="subtitle">Enlist a hero character or invite players into this campaign.</p>

          <div class="nav-tabs" style="margin-bottom: 1rem;">
            <div class="tab-item" [class.active]="addMemberTab === 'existing'" (click)="addMemberTab = 'existing'">📜 Vault Heroes</div>
            <div class="tab-item" [class.active]="addMemberTab === 'custom'" (click)="addMemberTab = 'custom'">✏️ Custom Hero</div>
            <div class="tab-item" [class.active]="addMemberTab === 'invite'" (click)="addMemberTab = 'invite'">🔑 Invite Code</div>
          </div>

          <!-- TAB 1: EXISTING HERO FROM VAULT -->
          <div *ngIf="addMemberTab === 'existing'" class="form-group">
            <label>Select Player Hero from Vault:</label>
            <select class="phyrexian-select" [(ngModel)]="selectedExistingCharId" style="margin-bottom: 0.8rem; width: 100%;">
              <option value="">-- Choose a Hero --</option>
              <option *ngFor="let c of charState.filteredCharacters()" [value]="c.char_id">
                {{ c.char_name }} (Lvl {{ c.char_level }} {{ c.char_class }}) - HP: {{ c.hp_max }}, AC: {{ c.armor_class }}
              </option>
            </select>

            <div *ngIf="getSelectedHero() as selectedHero" class="preview-mini-card" style="background: rgba(0,0,0,0.3); padding: 0.8rem; border-radius: 6px; border: 1px solid var(--border-card); margin-top: 0.5rem;">
              <div style="display: flex; gap: 0.8rem; align-items: center;">
                <img [src]="selectedHero.char_portrait || 'https://img.icons8.com/color/96/knight.png'" style="width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 1px solid var(--theme-accent);" />
                <div>
                  <h4 style="margin: 0; color: var(--theme-accent);">{{ selectedHero.char_name }}</h4>
                  <span style="font-size: 0.8rem; color: var(--text-muted);">Lvl {{ selectedHero.char_level }} {{ selectedHero.char_class }} ({{ selectedHero.race }})</span>
                  <div style="font-size: 0.8rem; margin-top: 0.2rem; color: var(--accent-gold);">
                    🛡️ AC: {{ selectedHero.armor_class }} | ❤️ HP: {{ selectedHero.hp_max }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- TAB 2: CUSTOM MANUAL HERO -->
          <div *ngIf="addMemberTab === 'custom'">
            <div class="form-group">
              <label>Character Name:</label>
              <input type="text" class="phyrexian-input" [(ngModel)]="newMemberName" placeholder="e.g. Minsc & Boo" />
            </div>

            <div class="form-row">
              <div>
                <label>Class:</label>
                <input type="text" class="phyrexian-input" [(ngModel)]="newMemberClass" placeholder="Ranger" />
              </div>
              <div>
                <label>Level:</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="newMemberLevel" min="1" max="20" style="width: 80px;" />
              </div>
            </div>

            <div class="form-row" style="margin-top: 0.8rem;">
              <div>
                <label>Max HP:</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="newMemberHp" style="width: 100px;" />
              </div>
              <div>
                <label>Armor Class (AC):</label>
                <input type="number" class="phyrexian-input" [(ngModel)]="newMemberAc" style="width: 100px;" />
              </div>
            </div>
          </div>

          <!-- TAB 3: INVITE CODE -->
          <div *ngIf="addMemberTab === 'invite'" class="invite-info-box" style="text-align: center; background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-card);">
            <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 0.5rem;">
              Invite players to join <strong>{{ campaignName }}</strong> from their Player Dashboard:
            </p>
            <div style="font-size: 1.6rem; font-weight: 800; letter-spacing: 4px; color: var(--accent-gold); background: rgba(212,175,55,0.15); border: 1px solid var(--accent-gold); padding: 0.5rem 1rem; border-radius: 8px; display: inline-block; margin-bottom: 0.75rem;">
              {{ inviteCode || '4D0705' }}
            </div>
            <br />
            <button class="phyrexian-btn-secondary mini-btn" (click)="copyInviteCode()" style="margin-bottom: 0.75rem;">
              📋 Copy Invite Code
            </button>
            <ol style="text-align: left; font-size: 0.82rem; color: var(--text-muted); line-height: 1.5; margin-left: 1rem; margin-top: 0.5rem;">
              <li>Players log into their account on the web app.</li>
              <li>Navigate to <strong>Player Dashboard</strong> and click <strong>🔑 Join Campaign</strong>.</li>
              <li>Enter invite code <strong style="color: var(--accent-gold);">{{ inviteCode || '4D0705' }}</strong> to join this realm.</li>
            </ol>
          </div>

          <div class="modal-actions">
            <button class="phyrexian-btn-secondary" (click)="showAddMemberModal = false">Cancel</button>
            <button *ngIf="addMemberTab === 'existing'" class="phyrexian-btn" [disabled]="!selectedExistingCharId" (click)="addExistingPartyMember()">Enlist Selected Hero</button>
            <button *ngIf="addMemberTab === 'custom'" class="phyrexian-btn" (click)="addPartyMember()">Add Custom Hero</button>
            <button *ngIf="addMemberTab === 'invite'" class="phyrexian-btn" (click)="copyInviteCode()">Copy Code & Close</button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .campaign-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .campaign-selector-row { display: flex; align-items: center; gap: 0.75rem; }
    .campaign-select { font-size: 1.1rem; font-weight: 700; color: var(--theme-accent); border: 1px solid var(--theme-accent); padding: 0.3rem 0.6rem; }
    .invite-badge { font-size: 0.8rem; background: rgba(212, 175, 55, 0.15); color: var(--accent-gold); border: 1px solid var(--accent-gold); padding: 0.2rem 0.6rem; border-radius: 12px; margin-left: 1rem; }
    .campaign-actions { display: flex; gap: 0.75rem; }
    .section-header { display: flex; justify-content: space-between; align-items: center; }
    .party-header-btns { display: flex; gap: 0.5rem; }
    .empty-party-card { background: rgba(0, 0, 0, 0.3); border: 1px border-dashed var(--border-card); padding: 2rem; text-align: center; border-radius: 8px; margin-bottom: 1.5rem; }
    .empty-party-card p { margin-bottom: 1rem; color: var(--text-muted); font-size: 1rem; }
    .subtitle { color: var(--text-muted); margin-bottom: 1rem; }
    .party-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
    .party-card { background: rgba(0, 0, 0, 0.4); border: 1px solid var(--border-card); border-radius: 8px; padding: 1rem; }
    .member-title { display: flex; align-items: center; gap: 0.6rem; }
    .mini-portrait { width: 36px; height: 36px; border-radius: 50%; object-fit: cover; border: 1px solid var(--theme-accent); }
    .card-header { display: flex; justify-content: space-between; align-items: center; }
    .class-tag { font-size: 0.75rem; color: var(--text-muted); }
    .vitals-row { display: flex; gap: 1rem; font-size: 0.8rem; color: var(--text-muted); margin: 0.5rem 0; }
    .hp-row { display: flex; align-items: center; gap: 0.5rem; }
    .hp-btn { width: 22px; height: 22px; cursor: pointer; background: rgba(255,255,255,0.1); border: 1px solid var(--border-card); color: #fff; border-radius: 4px; }
    .mini-hp-input { width: 55px; padding: 0.2rem; text-align: center; }
    .stat-rolls-section { margin-top: 0.5rem; }
    .section-sublabel { font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; }
    .mini-stat-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 0.2rem; margin-top: 0.2rem; }
    .mini-stat-btn { font-size: 0.65rem; padding: 0.15rem; text-align: center; justify-content: center; }
    .conditions-row { display: flex; gap: 0.3rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .cond-badge { font-size: 0.65rem; padding: 0.15rem 0.4rem; border-radius: 4px; background: rgba(255, 255, 255, 0.1); cursor: pointer; }
    .cond-badge.active { background: var(--primary-red); color: #fff; }
    .init-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
    .init-actions { display: flex; gap: 0.5rem; }
    .add-combatant-row { display: flex; gap: 0.75rem; margin-bottom: 1rem; }
    .init-table { width: 100%; border-collapse: collapse; }
    .init-table th, .init-table td { padding: 0.6rem; text-align: left; border-bottom: 1px solid var(--border-card); }
    .active-turn { background: rgba(255, 75, 75, 0.15); border-left: 3px solid var(--theme-accent); }
    .turn-indicator { font-weight: 700; color: var(--theme-accent); font-size: 0.75rem; }
    .combatant-name-cell { display: flex; align-items: center; gap: 0.5rem; }
    .hp-cell { display: flex; align-items: center; gap: 0.3rem; }
    .action-cell-btns { display: flex; gap: 0.5rem; align-items: center; }
    .clear-btn { background: none; border: none; color: #ff4b4b; cursor: pointer; font-size: 0.8rem; }
    .form-row { display: flex; gap: 1rem; align-items: center; margin-top: 0.5rem; }
    .result-box { margin-top: 1rem; background: rgba(0, 0, 0, 0.4); padding: 1rem; border-radius: 8px; }
    .modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.75); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-card { width: 100%; max-width: 480px; }
    .wide-modal { max-width: 650px; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; }
    .full-btn { width: 100%; }
    .mini-btn { font-size: 0.75rem; padding: 0.3rem; }
    .secret-checkbox { font-size: 0.85rem; cursor: pointer; color: var(--accent-gold); display: flex; align-items: center; gap: 0.4rem; margin-top: 0.5rem; }
  `]
})
export class DmComponent implements OnInit {
  activeTab: 'notes' | 'party' | 'initiative' | 'generators' | 'prep' = 'party';
  userCampaigns: any[] = [];
  campaignName = 'The Obsidian Citadel';
  campaignNotes = 'Chapter 3: The heroes enter the Sunless Citadel in search of the lost Gulthias Tree...';
  inviteCode = '';

  showWhisperModal = false;
  showRollModal = false;
  showNewCampaignModal = false;
  showAddMemberModal = false;

  newCampaignTitle = '';
  newCampaignNotes = '';

  newMemberName = '';
  newMemberClass = 'Fighter';
  newMemberLevel = 5;
  newMemberHp = 40;
  newMemberAc = 16;

  selectedStatblockCombatant: InitiativeCombatant | null = null;

  whisperRecipient = 'All';
  whisperMessage = '';

  rollTargetMember = 'Valeros';
  rollType = 'saving_throw';
  rollStat = 'DEX';
  rollReason = 'Dragon Breath Fire Save';
  isSecretRoll = false;

  avgLevel = 5;
  location = 'Crypt';
  encounterResult: any = null;

  npcConcept = 'Shady underworld broker';
  npcResult = '';

  prepNotes = '';
  prepResult = '';

  availableConditions = ['Poisoned', 'Concentrating', 'Stunned', 'Unconscious', 'Blinded', 'Charmed', 'Frightened', 'Grappled', 'Incapacitated', 'Invisible', 'Paralyzed', 'Petrified', 'Prone', 'Restrained'];

  // Unique campaign party rosters
  campaignParties: { [campaignName: string]: PartyMember[] } = {
    'The Obsidian Citadel': [
      { name: 'Valeros', char_class: 'Paladin', level: 5, hp_current: 44, hp_max: 44, ac: 18, passive_perception: 14, conditions: ['Concentrating'], stats: { STR: 18, DEX: 12, CON: 15, INT: 10, WIS: 14, CHA: 16 } },
      { name: 'Ezren', char_class: 'Wizard', level: 5, hp_current: 28, hp_max: 28, ac: 13, passive_perception: 12, conditions: [], stats: { STR: 10, DEX: 14, CON: 12, INT: 18, WIS: 13, CHA: 10 } },
      { name: 'Merisiel', char_class: 'Rogue', level: 5, hp_current: 35, hp_max: 35, ac: 16, passive_perception: 16, conditions: [], stats: { STR: 12, DEX: 18, CON: 14, INT: 12, WIS: 14, CHA: 12 } },
    ],
    'Curse of Strahd': [
      { name: 'Ismark Kolyanovich', char_class: 'Fighter', level: 4, hp_current: 38, hp_max: 38, ac: 17, passive_perception: 12, conditions: [], stats: { STR: 16, DEX: 12, CON: 14, INT: 10, WIS: 11, CHA: 14 } },
      { name: 'Ireena Kolyana', char_class: 'Cleric', level: 3, hp_current: 24, hp_max: 24, ac: 15, passive_perception: 13, conditions: [], stats: { STR: 10, DEX: 14, CON: 12, INT: 12, WIS: 16, CHA: 15 } },
      { name: 'Rudolph van Richten', char_class: 'Ranger', level: 8, hp_current: 58, hp_max: 58, ac: 16, passive_perception: 18, conditions: [], stats: { STR: 11, DEX: 16, CON: 13, INT: 16, WIS: 18, CHA: 14 } },
    ],
    'Phyrexia Awakens': [
      { name: 'Elspeth Tirel', char_class: 'Paladin', level: 7, hp_current: 64, hp_max: 64, ac: 20, passive_perception: 15, conditions: [], stats: { STR: 18, DEX: 12, CON: 16, INT: 11, WIS: 14, CHA: 18 } },
      { name: 'Karn', char_class: 'Barbarian', level: 8, hp_current: 85, hp_max: 85, ac: 18, passive_perception: 13, conditions: [], stats: { STR: 20, DEX: 14, CON: 18, INT: 14, WIS: 12, CHA: 10 } },
      { name: 'Teferi', char_class: 'Wizard', level: 7, hp_current: 42, hp_max: 42, ac: 14, passive_perception: 17, conditions: [], stats: { STR: 9, DEX: 14, CON: 14, INT: 20, WIS: 16, CHA: 13 } },
    ]
  };

  partyMembers: PartyMember[] = [];
  combatants: InitiativeCombatant[] = [];
  activeTurnIndex = 0;

  newCombatantName = '';
  newCombatantInit = 10;
  newCombatantHp = 20;

  addMemberTab: 'existing' | 'custom' | 'invite' = 'existing';
  selectedExistingCharId = '';

  constructor(
    private rollToast: RollToastService,
    private http: HttpClient,
    public charState: CharacterStateService,
    private wsService: WebSocketService
  ) {}

  ngOnInit() {
    this.loadCampaigns();
    this.generateInviteCode();
    this.charState.loadCharacters().subscribe();
  }

  loadCampaigns() {
    this.http.get<any[]>(`${environment.apiBaseUrl}/campaigns/`).subscribe({
      next: (camps) => {
        this.userCampaigns = camps || [];
        if (this.userCampaigns.length > 0 && !this.userCampaigns.some((c) => c.campaign_name === this.campaignName)) {
          this.campaignName = this.userCampaigns[0].campaign_name;
        }
        this.onCampaignSelect();
      },
      error: () => {
        this.userCampaigns = [
          { campaign_name: 'The Obsidian Citadel', invite_code: '4D0705', notes: 'Chapter 3: The heroes enter the Sunless Citadel...' },
          { campaign_name: 'Curse of Strahd', invite_code: 'BAROV1', notes: 'Chapter 1: Mist creeps into Castle Ravenloft...' },
          { campaign_name: 'Phyrexia Awakens', invite_code: 'PHY001', notes: 'Chapter 1: The glistened oil spreads...' }
        ];
        this.onCampaignSelect();
      }
    });
  }

  onCampaignSelect() {
    const selected = this.userCampaigns.find((c) => c.campaign_name === this.campaignName);
    if (selected) {
      this.inviteCode = selected.invite_code || '';
      if (selected.notes) this.campaignNotes = selected.notes;
    } else {
      this.generateInviteCode();
    }

    this.wsService.connect(this.campaignName);

    this.http.get<any[]>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/party`).subscribe({
      next: (chars) => {
        this.partyMembers = chars.map(char => ({
          char_id: char.char_id,
          name: char.char_name || 'Unknown',
          char_class: char.char_class || 'Unknown',
          level: char.char_level || 1,
          hp_current: char.hp_current ?? char.hp_max ?? 10,
          hp_max: char.hp_max ?? 10,
          ac: char.armor_class ?? 10,
          passive_perception: 10 + Math.floor(((char.stats?.WIS || 10) - 10) / 2),
          conditions: [],
          stats: char.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 },
          portrait: char.char_portrait
        }));
        this.campaignParties[this.campaignName] = [...this.partyMembers];

        if (this.partyMembers.length > 0) {
          this.rollTargetMember = this.partyMembers[0].name;
        }
        this.importPartyToInitiative(true);
      },
      error: () => {
        if (this.campaignParties[this.campaignName]) {
          this.partyMembers = [...this.campaignParties[this.campaignName]];
        } else {
          this.partyMembers = [];
        }
        if (this.partyMembers.length > 0) {
          this.rollTargetMember = this.partyMembers[0].name;
        }
        this.importPartyToInitiative(true);
      }
    });

    this.rollToast.showMessage('🏰 CAMPAIGN SWITCHED', `Active workspace set to "${this.campaignName}".`);
  }

  getSelectedHero() {
    if (!this.selectedExistingCharId) return null;
    return this.charState.characters().find((c) => c.char_id === this.selectedExistingCharId) || null;
  }

  addExistingPartyMember() {
    const char = this.getSelectedHero();
    if (!char) return;

    const member: PartyMember = {
      char_id: char.char_id,
      name: char.char_name,
      char_class: char.char_class,
      level: char.char_level,
      hp_current: char.hp_current ?? char.hp_max,
      hp_max: char.hp_max,
      ac: char.armor_class,
      passive_perception: 10 + Math.floor(((char.stats?.WIS || 10) - 10) / 2),
      conditions: [],
      stats: char.stats || { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 },
      portrait: char.char_portrait
    };

    if (!this.partyMembers.some((m) => m.name === member.name)) {
      this.partyMembers.push(member);
      if (!this.campaignParties[this.campaignName]) {
        this.campaignParties[this.campaignName] = [];
      }
      this.campaignParties[this.campaignName] = [...this.partyMembers];
      this.importPartyToInitiative();
      this.rollToast.showMessage('👤 HERO ENLISTED', `Added ${member.name} (${member.char_class}) to ${this.campaignName} party roster.`);
    } else {
      this.rollToast.showMessage('⚠️ ALREADY IN PARTY', `${member.name} is already in the active party roster.`);
    }
    this.showAddMemberModal = false;
    this.selectedExistingCharId = '';
  }

  copyInviteCode() {
    const code = this.inviteCode || '4D0705';
    navigator.clipboard.writeText(code);
    this.rollToast.showMessage('📋 CODE COPIED', `Invite code "${code}" copied to clipboard! Share with players.`);
    this.showAddMemberModal = false;
  }

  addPartyMember() {
    if (!this.newMemberName.trim()) return;
    const member: PartyMember = {
      name: this.newMemberName.trim(),
      char_class: this.newMemberClass || 'Fighter',
      level: this.newMemberLevel || 5,
      hp_current: this.newMemberHp || 40,
      hp_max: this.newMemberHp || 40,
      ac: this.newMemberAc || 16,
      passive_perception: 10 + Math.floor(((12) - 10) / 2),
      conditions: [],
      stats: { STR: 14, DEX: 14, CON: 14, INT: 10, WIS: 12, CHA: 10 }
    };

    this.partyMembers.push(member);
    if (!this.campaignParties[this.campaignName]) {
      this.campaignParties[this.campaignName] = [];
    }
    this.campaignParties[this.campaignName] = [...this.partyMembers];

    this.showAddMemberModal = false;
    this.newMemberName = '';
    this.importPartyToInitiative();
    this.rollToast.showMessage('👤 HERO ENLISTED', `Added ${member.name} (${member.char_class}) to ${this.campaignName} party roster.`);
  }

  createNewCampaign() {
    if (!this.newCampaignTitle.trim()) return;
    const newCamp = {
      campaign_name: this.newCampaignTitle.trim(),
      notes: this.newCampaignNotes,
      party: [],
      dnd_edition: '2014 Edition'
    };

    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/`, newCamp).subscribe({
      next: (res) => {
        this.userCampaigns.push(res);
        this.campaignName = res.campaign_name;
        this.campaignNotes = res.notes || '';
        this.showNewCampaignModal = false;
        this.newCampaignTitle = '';
        this.newCampaignNotes = '';
        this.generateInviteCode();
        this.rollToast.showMessage('🏰 CAMPAIGN CREATED', `Successfully forged campaign: ${res.campaign_name}`);
      },
      error: () => {
        // Local state fallback
        this.userCampaigns.push(newCamp);
        this.campaignName = newCamp.campaign_name;
        this.showNewCampaignModal = false;
        this.newCampaignTitle = '';
        this.newCampaignNotes = '';
        this.rollToast.showMessage('🏰 CAMPAIGN CREATED', `Created campaign locally: ${newCamp.campaign_name}`);
      }
    });
  }

  saveCampaignNotes() {
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/notes`, {
      notes: this.campaignNotes
    }).subscribe({
      next: () => this.rollToast.showMessage('📝 NOTES SAVED', 'Campaign notes auto-saved to database.'),
      error: () => this.rollToast.showMessage('⚠️ SAVE FAILED', 'Failed to save campaign notes.')
    });
  }

  generateInviteCode() {
    this.http.post<any>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/invite-code`, {}).subscribe((res) => {
      this.inviteCode = res.invite_code;
    });
  }

  adjustHp(member: PartyMember, delta: number) {
    member.hp_current = Math.max(0, Math.min(member.hp_max, member.hp_current + delta));
  }

  toggleCondition(member: PartyMember, cond: string) {
    const idx = member.conditions.indexOf(cond);
    if (idx >= 0) member.conditions.splice(idx, 1);
    else member.conditions.push(cond);
  }

  quickDmStatRoll(member: PartyMember, stat: string) {
    const val = member.stats?.[stat] || 10;
    const mod = Math.floor((val - 10) / 2);
    const raw = Math.floor(Math.random() * 20) + 1;
    const total = raw + mod;
    const expr = `1d20 (${raw}) ${mod >= 0 ? '+' + mod : mod}`;

    this.rollToast.showRoll({
      title: `🎲 DM CHECK: ${member.name.toUpperCase()} (${stat})`,
      expression: expr,
      raw,
      modifier: mod,
      total
    });
  }

  openSingleRollModal(m: PartyMember) {
    this.rollTargetMember = m.name;
    this.showRollModal = true;
  }

  sendRollRequest() {
    this.showRollModal = false;
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/roll-request`, {
      char_filename: this.rollTargetMember.toLowerCase() + '.json',
      char_name: this.rollTargetMember,
      roll_type: this.rollType,
      stat: this.rollStat,
      reason: this.rollReason,
      is_secret: this.isSecretRoll
    }).subscribe(() => {
      const secTag = this.isSecretRoll ? ' 🔒 [SECRET]' : '';
      this.rollToast.showMessage('🎲 ROLL REQUEST SENT', `Issued ${this.rollType} (${this.rollStat}) to ${this.rollTargetMember}${secTag}.`);
    });
  }

  importPartyToInitiative(silent = false) {
    if (silent) {
      // Remove old campaign player combatants
      this.combatants = this.combatants.filter((c) => !c.is_player);
    }
    this.partyMembers.forEach((p) => {
      if (!this.combatants.some((c) => c.name === p.name)) {
        const dexVal = p.stats?.['DEX'] || 10;
        const dexMod = Math.floor((dexVal - 10) / 2);
        this.combatants.push({
          id: Math.random().toString(36).substring(2, 9),
          name: p.name,
          initiative: 10 + dexMod,
          hp: p.hp_current,
          max_hp: p.hp_max,
          ac: p.ac,
          dex: dexVal,
          is_player: true,
          portrait: p.portrait
        });
      }
    });
    this.sortCombatants();
    if (!silent) {
      this.rollToast.showMessage('👥 PARTY IMPORTED', 'Imported active party members into Initiative Tracker.');
    }
  }

  addCombatant() {
    if (!this.newCombatantName) return;
    this.combatants.push({
      id: Math.random().toString(36).substring(2, 9),
      name: this.newCombatantName,
      initiative: this.newCombatantInit,
      hp: this.newCombatantHp,
      max_hp: this.newCombatantHp,
      ac: 12,
      dex: 10,
      is_player: false,
    });
    this.sortCombatants();
    this.newCombatantName = '';
  }

  removeCombatant(idx: number) {
    this.combatants.splice(idx, 1);
  }

  rollAllInitiative() {
    this.combatants.forEach((c) => {
      const raw = Math.floor(Math.random() * 20) + 1;
      const dexMod = Math.floor((c.dex - 10) / 2);
      c.initiative = raw + dexMod;
    });
    this.sortCombatants();
    this.rollToast.showMessage('🎲 INITIATIVE ROLLED', 'Rolled initiative for all active combatants!');
  }

  sortCombatants() {
    this.combatants.sort((a, b) => b.initiative - a.initiative);
  }

  nextTurn() {
    if (this.combatants.length === 0) return;
    this.activeTurnIndex = (this.activeTurnIndex + 1) % this.combatants.length;
  }

  openStatblock(c: InitiativeCombatant) {
    this.selectedStatblockCombatant = c;
  }

  openBeyondUrl(name: string) {
    const slug = name.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/ /g, '-');
    window.open(`https://www.dndbeyond.com/monsters/${slug}`, '_blank');
  }

  generateEncounter() {
    this.http.post(`${environment.apiBaseUrl}/dm/encounter`, {
      party_size: 4,
      avg_level: this.avgLevel,
      location: this.location,
      edition: '2014 Edition',
      difficulty: 'Medium'
    }).subscribe((res) => {
      this.encounterResult = res;
    });
  }

  generateNpc() {
    this.http.post<any>(`${environment.apiBaseUrl}/dm/npc`, {
      npc_concept: this.npcConcept,
      edition: '2014 Edition'
    }).subscribe((res) => {
      this.npcResult = res.npc_markdown;
    });
  }

  generatePrep() {
    this.http.post<any>(`${environment.apiBaseUrl}/dm/session-prep`, {
      campaign_notes: this.prepNotes,
      party_info: this.partyMembers.map(m => m.name).join(', ')
    }).subscribe((res) => {
      this.prepResult = res.prep_markdown;
    });
  }

  sendWhisper() {
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/whisper`, {
      sender: 'DM',
      recipient: this.whisperRecipient,
      message: this.whisperMessage
    }).subscribe(() => {
      this.showWhisperModal = false;
      this.rollToast.showMessage('💬 WHISPER SENT', `Whisper delivered to ${this.whisperRecipient}.`);
      this.whisperMessage = '';
    });
  }
}
