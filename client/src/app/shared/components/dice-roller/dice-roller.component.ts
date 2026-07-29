import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-dice-roller',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="phyrexian-card dice-panel">
      <div class="panel-header">
        <h3>🎲 Interactive Dice Roller</h3>
        <button class="clear-btn" (click)="rollHistory = []">🗑️ Clear History</button>
      </div>

      <div class="dice-buttons">
        <button class="dice-btn" (click)="roll(4)">d4</button>
        <button class="dice-btn" (click)="roll(6)">d6</button>
        <button class="dice-btn" (click)="roll(8)">d8</button>
        <button class="dice-btn" (click)="roll(10)">d10</button>
        <button class="dice-btn" (click)="roll(12)">d12</button>
        <button class="dice-btn highlight" (click)="roll(20)">d20</button>
        <button class="dice-btn" (click)="roll(100)">d100</button>
      </div>

      <div class="modifier-row">
        <label>Modifier (+/-):</label>
        <input type="number" class="phyrexian-input mod-input" [(ngModel)]="modifier" />
      </div>

      <!-- Last Roll Display -->
      <div *ngIf="lastRoll" class="last-roll-card">
        <span class="roll-label">Latest Result:</span>
        <span class="roll-result">{{ lastRoll.expression }} = <strong>{{ lastRoll.total }}</strong></span>
        <span class="roll-details">({{ lastRoll.rolls.join(', ') }} + {{ lastRoll.modifier }})</span>
      </div>

      <!-- History Log -->
      <div *ngIf="rollHistory.length > 0" class="history-log">
        <div *ngFor="let item of rollHistory.slice(0, 5)" class="history-item">
          <span>{{ item.expression }}</span>
          <span class="hist-total">{{ item.total }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .dice-panel {
      margin-top: 1.5rem;
    }
    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.75rem;
    }
    .clear-btn {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 0.75rem;
      cursor: pointer;
    }
    .clear-btn:hover { color: var(--theme-accent); }
    .dice-buttons {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 0.75rem;
    }
    .dice-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-card);
      color: var(--text-primary);
      padding: 0.4rem 0.8rem;
      border-radius: 6px;
      font-weight: 700;
      cursor: pointer;
      transition: all 0.2s;
    }
    .dice-btn:hover {
      background: var(--theme-accent);
      color: #fff;
    }
    .dice-btn.highlight {
      border-color: var(--theme-accent);
      color: var(--theme-accent);
    }
    .dice-btn.highlight:hover {
      color: #fff;
    }
    .modifier-row {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 0.85rem;
      color: var(--text-muted);
      margin-bottom: 0.75rem;
    }
    .mod-input {
      width: 70px;
    }
    .last-roll-card {
      background: rgba(255, 75, 75, 0.1);
      border: 1px solid var(--theme-accent);
      padding: 0.6rem 0.8rem;
      border-radius: 6px;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      margin-bottom: 0.5rem;
    }
    .roll-label { font-size: 0.8rem; color: var(--text-muted); }
    .roll-result { font-size: 1.1rem; color: var(--text-primary); }
    .roll-details { font-size: 0.75rem; color: var(--text-muted); }
    .history-log {
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
    }
    .history-item {
      font-size: 0.8rem;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      padding: 0.2rem 0.4rem;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 4px;
    }
    .hist-total { font-weight: 700; color: var(--theme-accent); }
  `]
})
export class DiceRollerComponent {
  modifier = 0;
  lastRoll: any = null;
  rollHistory: any[] = [];

  roll(sides: number) {
    const raw = Math.floor(Math.random() * sides) + 1;
    const total = raw + this.modifier;
    const expression = `1d${sides}${this.modifier >= 0 ? '+' + this.modifier : this.modifier}`;

    const rollData = {
      sides,
      rolls: [raw],
      modifier: this.modifier,
      total,
      expression,
    };

    this.lastRoll = rollData;
    this.rollHistory.unshift(rollData);
  }
}
