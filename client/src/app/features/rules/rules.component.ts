import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';

@Component({
  selector: 'app-rules',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="rules-container">
      <div class="phyrexian-card">
        <h2>📚 D&D Arcane Rules Library</h2>
        <p class="subtitle">Search rules, compare 2014 vs 2024 revisions, or run automated character build validation.</p>

        <div class="nav-tabs">
          <div class="tab-item" [class.active]="activeTab === 'oracle'" (click)="activeTab = 'oracle'">🔮 Rules Oracle</div>
          <div class="tab-item" [class.active]="activeTab === 'compare'" (click)="activeTab = 'compare'">⚖️ 2014 vs 2024 Edition Comparator</div>
          <div class="tab-item" [class.active]="activeTab === 'validate'" (click)="activeTab = 'validate'">🛡️ Character Rules Inspector</div>
        </div>

        <!-- TAB 1: RULES ORACLE -->
        <div *ngIf="activeTab === 'oracle'" class="tab-body">
          <div class="search-row">
            <input type="text" class="phyrexian-input" [(ngModel)]="oracleQuery" placeholder="Ask any rule question (e.g., How does grapple work in 5.5e?)" (keyup.enter)="searchOracle()" />
            <button class="phyrexian-btn" (click)="searchOracle()">Search Oracle</button>
          </div>

          <div *ngIf="oracleAnswer" class="result-box">
            <p style="white-space: pre-wrap;">{{ oracleAnswer }}</p>
          </div>
        </div>

        <!-- TAB 2: EDITION COMPARATOR -->
        <div *ngIf="activeTab === 'compare'" class="tab-body">
          <div class="search-row">
            <input type="text" class="phyrexian-input" [(ngModel)]="compareQuery" placeholder="Enter feature or spell to compare (e.g. Paladin Smite, Counterspell)" (keyup.enter)="compareEditions()" />
            <button class="phyrexian-btn" (click)="compareEditions()">Compare Editions</button>
          </div>

          <div *ngIf="compareAnswer" class="result-box">
            <p style="white-space: pre-wrap;">{{ compareAnswer }}</p>
          </div>
        </div>

        <!-- TAB 3: CHARACTER BUILD RULES INSPECTOR -->
        <div *ngIf="activeTab === 'validate'" class="tab-body">
          <p class="subtitle">Inspect the currently selected hero for D&D 5e/5.5e rule compliance (ability score bounds, spell slot allocations, proficiencies).</p>
          <button class="phyrexian-btn" (click)="validateActiveHero()">🛡️ Run Build Audit</button>

          <div *ngIf="validationResult" class="result-box audit-card" [class.valid-audit]="validationResult.valid">
            <div class="audit-status-banner">
              <span *ngIf="validationResult.valid" class="status-pass">✅ BUILD PASSED ALL 5E/5.5E RULES AUDITS</span>
              <span *ngIf="!validationResult.valid" class="status-fail">⚠️ BUILD AUDIT DISCREPANCIES DETECTED</span>
            </div>

            <div *ngIf="validationResult.errors?.length > 0" class="audit-issues-list">
              <h4>Detected Audit Discrepancies:</h4>
              <ul>
                <li *ngFor="let err of validationResult.errors" class="issue-item">⚠️ {{ err }}</li>
              </ul>
            </div>

            <div *ngIf="validationResult.valid" class="audit-pass-info">
              <p>Character statistics, ability bounds (3 to 20), proficiency bonuses, and armor class comply with core 5e specifications.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .rules-container { max-width: 850px; margin: 0 auto; }
    .subtitle { color: var(--text-muted); margin-bottom: 1.5rem; }
    .search-row { display: flex; gap: 0.75rem; margin-top: 1rem; }
    .search-row input { flex: 1; }
    .result-box { margin-top: 1.5rem; background: rgba(0, 0, 0, 0.4); border: 1px solid var(--border-card); padding: 1.25rem; border-radius: 8px; font-size: 0.9rem; line-height: 1.6; }
    .tab-body { margin-top: 1rem; }
    .audit-card { border-left: 4px solid var(--theme-accent); }
    .audit-card.valid-audit { border-left-color: var(--accent-emerald, #2ecc71); }
    .audit-status-banner { font-size: 1rem; font-weight: 800; margin-bottom: 0.75rem; }
    .status-pass { color: #2ecc71; }
    .status-fail { color: #ff4b4b; }
    .audit-issues-list h4 { font-size: 0.88rem; color: var(--text-gold); margin-bottom: 0.4rem; }
    .issue-item { color: #ff4b4b; margin-left: 1.2rem; margin-top: 0.2rem; }
    .audit-pass-info { font-size: 0.88rem; color: var(--text-muted); }
  `]
})
export class RulesComponent {
  activeTab: 'oracle' | 'compare' | 'validate' = 'oracle';
  oracleQuery = '';
  oracleAnswer = '';

  compareQuery = 'Paladin divine smite';
  compareAnswer = '';

  validationResult: any = null;

  constructor(
    private http: HttpClient,
    public charState: CharacterStateService,
    private rollToast: RollToastService
  ) {}

  searchOracle() {
    if (!this.oracleQuery) return;
    this.http.post<any>('http://localhost:8000/api/v1/rules/query', {
      query: this.oracleQuery,
      edition: this.charState.dndEdition()
    }).subscribe((res) => {
      this.oracleAnswer = res.answer_markdown;
      this.rollToast.showMessage('🔮 ORACLE SEARCH COMPLETE', `Retrieved rules for "${this.oracleQuery}".`);
    });
  }

  compareEditions() {
    if (!this.compareQuery) return;
    this.http.post<any>('http://localhost:8000/api/v1/rules/compare', {
      query: this.compareQuery
    }).subscribe((res) => {
      this.compareAnswer = res.comparison_markdown;
      this.rollToast.showMessage('⚖️ EDITION COMPARISON', `Compared 2014 vs 2024 rules for "${this.compareQuery}".`);
    });
  }

  validateActiveHero() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>('http://localhost:8000/api/v1/rules/validate', {
      character: char
    }).subscribe((res) => {
      this.validationResult = res.validation_result;
      const statusText = res.validation_result?.valid ? 'PASSED' : 'DISCREPANCIES DETECTED';
      this.rollToast.showMessage('🛡️ BUILD AUDIT COMPLETE', `Audit status for ${char.char_name}: ${statusText}`);
    });
  }
}
