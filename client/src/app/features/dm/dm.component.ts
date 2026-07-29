import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

export interface PartyMember {
  name: string;
  char_class: string;
  level: number;
  hp_current: number;
  hp_max: number;
  ac: number;
  passive_perception: number;
  conditions: string[];
}

export interface InitiativeCombatant {
  name: string;
  initiative: number;
  hp: number;
  is_player: boolean;
}

@Component({
  selector: 'app-dm',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="dm-container">
      <div class="phyrexian-card campaign-header">
        <div class="campaign-info">
          <h2>🏰 Campaign Workspace: {{ campaignName }}</h2>
          <span class="invite-badge" *ngIf="inviteCode">Invite Code: <strong>{{ inviteCode }}</strong></span>
        </div>
        <div class="campaign-actions">
          <button class="phyrexian-btn-secondary" (click)="generateInviteCode()">🔑 Generate Invite Code</button>
          <button class="phyrexian-btn" (click)="showWhisperModal = true">💬 Send Whisper</button>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="nav-tabs">
        <div class="tab-item" [class.active]="activeTab === 'party'" (click)="activeTab = 'party'">👥 Live Party Tracker</div>
        <div class="tab-item" [class.active]="activeTab === 'initiative'" (click)="activeTab = 'initiative'">⚔️ Initiative Tracker</div>
        <div class="tab-item" [class.active]="activeTab === 'generators'" (click)="activeTab = 'generators'">🎲 AI Generators</div>
        <div class="tab-item" [class.active]="activeTab === 'prep'" (click)="activeTab = 'prep'">📜 Session Prep</div>
      </div>

      <!-- TAB 1: PARTY TRACKER -->
      <div *ngIf="activeTab === 'party'" class="phyrexian-card">
        <h3>👥 Active Party Roster</h3>
        <p class="subtitle">Monitor health, status conditions, and send roll requests.</p>
        
        <div class="party-grid">
          <div class="party-card" *ngFor="let m of partyMembers">
            <div class="card-header">
              <h4>{{ m.name }}</h4>
              <span class="class-tag">Lvl {{ m.level }} {{ m.char_class }}</span>
            </div>
            
            <div class="vitals-row">
              <span>🛡️ AC: {{ m.ac }}</span>
              <span>👁️ Perception: {{ m.passive_perception }}</span>
            </div>

            <div class="hp-row">
              <label>HP:</label>
              <button class="hp-btn" (click)="adjustHp(m, -1)">-</button>
              <span class="hp-val">{{ m.hp_current }} / {{ m.hp_max }}</span>
              <button class="hp-btn" (click)="adjustHp(m, 1)">+</button>
            </div>

            <div class="conditions-row">
              <span 
                *ngFor="let cond of availableConditions" 
                class="cond-badge" 
                [class.active]="m.conditions.includes(cond)"
                (click)="toggleCondition(m, cond)">
                {{ cond }}
              </span>
            </div>

            <button class="phyrexian-btn-secondary full-btn mini-btn" style="margin-top: 0.75rem;" (click)="requestRoll(m)">
              🎲 Request Roll
            </button>
          </div>
        </div>
      </div>

      <!-- TAB 2: INITIATIVE TRACKER -->
      <div *ngIf="activeTab === 'initiative'" class="phyrexian-card">
        <div class="init-header">
          <h3>⚔️ Initiative Combat Tracker</h3>
          <div class="init-actions">
            <button class="phyrexian-btn-secondary" (click)="rollAllInitiative()">🎲 Roll All</button>
            <button class="phyrexian-btn" (click)="nextTurn()">Next Turn ➡️</button>
          </div>
        </div>

        <div class="add-combatant-row">
          <input type="text" class="phyrexian-input" placeholder="Combatant Name" [(ngModel)]="newCombatantName" />
          <input type="number" class="phyrexian-input" placeholder="Init Score" [(ngModel)]="newCombatantInit" style="width: 100px;" />
          <button class="phyrexian-btn" (click)="addCombatant()">+ Add</button>
        </div>

        <table class="init-table" *ngIf="combatants.length > 0">
          <thead>
            <tr>
              <th>Turn</th>
              <th>Combatant</th>
              <th>Initiative</th>
              <th>HP</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let c of combatants; let i = index" [class.active-turn]="i === activeTurnIndex">
              <td><span *ngIf="i === activeTurnIndex" class="turn-indicator">⚔️ CURRENT</span></td>
              <td><strong>{{ c.name }}</strong></td>
              <td>{{ c.initiative }}</td>
              <td>{{ c.hp }}</td>
              <td>
                <button class="clear-btn" (click)="removeCombatant(i)">❌ Remove</button>
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
            <p>{{ npcResult }}</p>
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
          <p>{{ prepResult }}</p>
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
    </div>
  `,
  styles: [`
    .campaign-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 1.5rem;
    }
    .invite-badge {
      font-size: 0.8rem;
      background: rgba(212, 175, 55, 0.15);
      color: var(--accent-gold);
      border: 1px solid var(--accent-gold);
      padding: 0.2rem 0.6rem;
      border-radius: 12px;
      margin-left: 1rem;
    }
    .campaign-actions { display: flex; gap: 0.75rem; }
    .subtitle { color: var(--text-muted); margin-bottom: 1rem; }
    .party-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
    }
    .party-card {
      background: rgba(0, 0, 0, 0.4);
      border: 1px solid var(--border-card);
      border-radius: 8px;
      padding: 1rem;
    }
    .card-header { display: flex; justify-content: space-between; align-items: center; }
    .class-tag { font-size: 0.75rem; color: var(--text-muted); }
    .vitals-row { display: flex; gap: 1rem; font-size: 0.8rem; color: var(--text-muted); margin: 0.5rem 0; }
    .hp-row { display: flex; align-items: center; gap: 0.5rem; }
    .hp-btn { width: 22px; height: 22px; cursor: pointer; background: rgba(255,255,255,0.1); border: 1px solid var(--border-card); color: #fff; border-radius: 4px; }
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
    .clear-btn { background: none; border: none; color: #ff4b4b; cursor: pointer; font-size: 0.8rem; }
    .form-row { display: flex; gap: 1rem; align-items: center; margin-top: 0.5rem; }
    .result-box { margin-top: 1rem; background: rgba(0, 0, 0, 0.4); padding: 1rem; border-radius: 8px; }
    .modal-backdrop { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.75); display: flex; justify-content: center; align-items: center; z-index: 1000; }
    .modal-card { width: 100%; max-width: 450px; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 0.75rem; margin-top: 1rem; }
    .full-btn { width: 100%; }
    .mini-btn { font-size: 0.75rem; padding: 0.3rem; }
  `]
})
export class DmComponent implements OnInit {
  activeTab: 'party' | 'initiative' | 'generators' | 'prep' = 'party';
  campaignName = 'The Obsidian Citadel';
  inviteCode = '';
  showWhisperModal = false;

  whisperRecipient = 'All';
  whisperMessage = '';

  avgLevel = 5;
  location = 'Crypt';
  encounterResult: any = null;

  npcConcept = 'Shady underworld broker';
  npcResult = '';

  prepNotes = '';
  prepResult = '';

  availableConditions = ['Poisoned', 'Concentrating', 'Stunned', 'Unconscious'];

  partyMembers: PartyMember[] = [
    { name: 'Valeros', char_class: 'Paladin', level: 5, hp_current: 44, hp_max: 44, ac: 18, passive_perception: 14, conditions: ['Concentrating'] },
    { name: 'Ezren', char_class: 'Wizard', level: 5, hp_current: 28, hp_max: 28, ac: 13, passive_perception: 12, conditions: [] },
    { name: 'Merisiel', char_class: 'Rogue', level: 5, hp_current: 35, hp_max: 35, ac: 16, passive_perception: 16, conditions: [] },
  ];

  combatants: InitiativeCombatant[] = [
    { name: 'Merisiel', initiative: 21, hp: 35, is_player: true },
    { name: 'Valeros', initiative: 16, hp: 44, is_player: true },
    { name: 'Goblin Warlord', initiative: 14, hp: 30, is_player: false },
    { name: 'Ezren', initiative: 9, hp: 28, is_player: true },
  ];
  activeTurnIndex = 0;

  newCombatantName = '';
  newCombatantInit = 10;

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.generateInviteCode();
  }

  generateInviteCode() {
    this.http.post<any>(`http://localhost:8000/api/v1/campaigns/${this.campaignName}/invite-code`, {}).subscribe((res) => {
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

  requestRoll(member: PartyMember) {
    this.http.post(`http://localhost:8000/api/v1/campaigns/${this.campaignName}/roll-request`, {
      char_filename: member.name.toLowerCase() + '.json',
      char_name: member.name,
      roll_type: 'saving_throw',
      stat: 'DEX',
      reason: 'Dragon Breath'
    }).subscribe(() => {
      alert(`Sent roll request to ${member.name}!`);
    });
  }

  addCombatant() {
    if (!this.newCombatantName) return;
    this.combatants.push({
      name: this.newCombatantName,
      initiative: this.newCombatantInit,
      hp: 20,
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
      c.initiative = Math.floor(Math.random() * 20) + 1;
    });
    this.sortCombatants();
  }

  sortCombatants() {
    this.combatants.sort((a, b) => b.initiative - a.initiative);
  }

  nextTurn() {
    if (this.combatants.length === 0) return;
    this.activeTurnIndex = (this.activeTurnIndex + 1) % this.combatants.length;
  }

  generateEncounter() {
    this.http.post('http://localhost:8000/api/v1/dm/encounter', {
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
    this.http.post<any>('http://localhost:8000/api/v1/dm/npc', {
      npc_concept: this.npcConcept,
      edition: '2014 Edition'
    }).subscribe((res) => {
      this.npcResult = res.npc_markdown;
    });
  }

  generatePrep() {
    this.http.post<any>('http://localhost:8000/api/v1/dm/session-prep', {
      campaign_notes: this.prepNotes,
      party_info: 'Valeros, Ezren, Merisiel'
    }).subscribe((res) => {
      this.prepResult = res.prep_markdown;
    });
  }

  sendWhisper() {
    this.showWhisperModal = false;
    alert(`Secret Whisper sent to ${this.whisperRecipient}: "${this.whisperMessage}"`);
    this.whisperMessage = '';
  }
}
