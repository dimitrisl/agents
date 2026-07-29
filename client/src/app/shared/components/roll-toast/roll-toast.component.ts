import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RollToastService } from '../../../core/services/roll-toast.service';

@Component({
  selector: 'app-roll-toast',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div *ngIf="rollService.activeRoll() as roll" class="roll-toast-overlay animated-fade">
      <div class="roll-toast-card phyrexian-card" [class.nat-20]="roll.isNat20" [class.nat-1]="roll.isNat1">
        <div class="toast-header">
          <span class="toast-title">{{ roll.title }}</span>
          <button class="toast-close" (click)="rollService.dismiss()">×</button>
        </div>

        <!-- Custom Message Notification -->
        <div *ngIf="roll.message" class="toast-message-body">
          <p>{{ roll.message }}</p>
        </div>

        <!-- Numeric Roll Result Notification -->
        <div *ngIf="!roll.message" class="toast-roll-body">
          <div class="roll-badge-col">
            <div class="d20-icon-wrapper" [class.rolling]="isRolling">
              <span class="raw-die" [class.gold-text]="roll.isNat20" [class.red-text]="roll.isNat1">
                🎲 {{ roll.raw }}
              </span>
            </div>
            <span *ngIf="roll.isNat20" class="crit-badge gold-badge animated-pulse">⭐ CRITICAL HIT!</span>
            <span *ngIf="roll.isNat1" class="crit-badge red-badge animated-pulse">💀 CRITICAL FAIL!</span>
          </div>

          <div class="roll-math">
            <span class="math-expr">{{ roll.expression }}</span>
            <span class="total-score" [class.gold-glow]="roll.isNat20" [class.red-glow]="roll.isNat1">{{ roll.total }}</span>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .roll-toast-overlay {
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      z-index: 9999;
      pointer-events: auto;
    }
    .roll-toast-card {
      min-width: 320px;
      max-width: 420px;
      background: rgba(14, 14, 22, 0.95);
      border: 2px solid var(--theme-accent);
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 20px rgba(255, 75, 75, 0.4);
      border-radius: 12px;
      padding: 1rem 1.25rem;
    }
    .roll-toast-card.nat-20 {
      border-color: var(--accent-gold);
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(212, 175, 55, 0.6);
    }
    .roll-toast-card.nat-1 {
      border-color: #ff4b4b;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.8), 0 0 25px rgba(255, 75, 75, 0.7);
    }
    .toast-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 0.5rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding-bottom: 0.4rem;
    }
    .toast-title {
      font-family: var(--font-title);
      font-size: 0.95rem;
      font-weight: 700;
      color: var(--text-gold);
      letter-spacing: 0.5px;
    }
    .toast-close {
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.4rem;
      cursor: pointer;
      line-height: 1;
    }
    .toast-close:hover { color: #fff; }
    .toast-message-body p {
      font-size: 0.9rem;
      color: var(--text-primary);
      margin: 0.3rem 0;
    }
    .toast-roll-body {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 0.5rem;
    }
    .roll-badge-col {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
    }
    .d20-icon-wrapper {
      transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .d20-icon-wrapper.rolling {
      transform: rotate(360deg) scale(1.15);
    }
    .raw-die {
      font-size: 1.4rem;
      font-weight: 800;
      color: var(--text-primary);
    }
    .gold-text { color: var(--accent-gold); }
    .red-text { color: #ff4b4b; }
    .crit-badge {
      font-size: 0.7rem;
      font-weight: 800;
      padding: 0.1rem 0.4rem;
      border-radius: 4px;
      margin-top: 0.2rem;
    }
    .gold-badge { background: rgba(212, 175, 55, 0.2); color: var(--accent-gold); border: 1px solid var(--accent-gold); }
    .red-badge { background: rgba(255, 75, 75, 0.2); color: #ff4b4b; border: 1px solid #ff4b4b; }
    .roll-math {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
    }
    .math-expr {
      font-size: 0.8rem;
      color: var(--text-muted);
    }
    .total-score {
      font-size: 2.2rem;
      font-weight: 900;
      color: var(--theme-accent);
      line-height: 1;
      text-shadow: 0 0 10px rgba(255, 75, 75, 0.5);
    }
    .gold-glow { color: var(--accent-gold); text-shadow: 0 0 12px rgba(212, 175, 55, 0.8); }
    .red-glow { color: #ff4b4b; text-shadow: 0 0 12px rgba(255, 75, 75, 0.8); }
  `]
})
export class RollToastComponent implements OnInit {
  isRolling = false;

  constructor(public rollService: RollToastService) {}

  ngOnInit() {
    this.isRolling = true;
    setTimeout(() => {
      this.isRolling = false;
    }, 300);
  }
}
