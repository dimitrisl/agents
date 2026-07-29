import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-dm',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="dm-container">
      <h2>🏰 Dungeon Master Workspace</h2>

      <div class="nav-tabs">
        <div class="tab-item" [class.active]="activeTab === 'tracker'" (click)="activeTab = 'tracker'">⚔️ Party & Initiative Tracker</div>
        <div class="tab-item" [class.active]="activeTab === 'generators'" (click)="activeTab = 'generators'">🎲 AI Encounter & NPC Generators</div>
      </div>

      <!-- Tab 1: Party Tracker -->
      <div *ngIf="activeTab === 'tracker'" class="phyrexian-card">
        <h3>👥 Active Campaign Roster</h3>
        <p class="subtitle">Monitor party hit points, conditions, and roll requests.</p>

        <div class="cards-grid">
          <div class="stat-box party-card">
            <h4>Valeros the Devout</h4>
            <p>HP: 44 / 44</p>
            <p>AC: 18 | Passive Perception: 14</p>
          </div>
        </div>
      </div>

      <!-- Tab 2: AI Generators -->
      <div *ngIf="activeTab === 'generators'" class="phyrexian-card">
        <h3>🎲 AI Encounter Generator</h3>
        <div class="form-row">
          <label>Party Level:</label>
          <input type="number" class="phyrexian-input" [(ngModel)]="avgLevel" />
          <label>Environment:</label>
          <input type="text" class="phyrexian-input" [(ngModel)]="location" />
          <button class="phyrexian-btn" (click)="generateEncounter()">Generate Encounter</button>
        </div>

        <div *ngIf="encounterResult" class="result-box">
          <pre>{{ encounterResult | json }}</pre>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .subtitle {
      color: var(--text-muted);
      margin-bottom: 1rem;
    }
    .cards-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 1rem;
    }
    .form-row {
      display: flex;
      gap: 1rem;
      align-items: center;
      margin-top: 1rem;
    }
    .result-box {
      margin-top: 1.5rem;
      background: rgba(0, 0, 0, 0.4);
      padding: 1rem;
      border-radius: 8px;
    }
  `]
})
export class DmComponent {
  activeTab: 'tracker' | 'generators' = 'tracker';
  avgLevel = 5;
  location = 'Crypt';
  encounterResult: any = null;

  constructor(private http: HttpClient) {}

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
}
