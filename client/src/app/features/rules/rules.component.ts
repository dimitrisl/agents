import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-rules',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="rules-container">
      <h2>📚 Rules Oracle & Edition Comparison</h2>

      <div class="nav-tabs">
        <div class="tab-item" [class.active]="activeTab === 'oracle'" (click)="activeTab = 'oracle'">🔮 Rules Oracle</div>
        <div class="tab-item" [class.active]="activeTab === 'compare'" (click)="activeTab = 'compare'">⚖️ 2014 vs 2024 Comparison</div>
      </div>

      <div *ngIf="activeTab === 'oracle'" class="phyrexian-card">
        <h3>Ask the Rules Oracle</h3>
        <div class="query-row">
          <input type="text" class="phyrexian-input" placeholder="e.g. How does Grappling work?" [(ngModel)]="query" (keyup.enter)="askOracle()" />
          <button class="phyrexian-btn" (click)="askOracle()">Consult Oracle</button>
        </div>

        <div *ngIf="oracleAnswer" class="answer-box">
          <p>{{ oracleAnswer }}</p>
        </div>
      </div>

      <div *ngIf="activeTab === 'compare'" class="phyrexian-card">
        <h3>Compare 2014 vs 2024 Revision</h3>
        <div class="query-row">
          <input type="text" class="phyrexian-input" placeholder="e.g. Counterspell changes" [(ngModel)]="compareQuery" (keyup.enter)="compareRules()" />
          <button class="phyrexian-btn" (click)="compareRules()">Compare</button>
        </div>

        <div *ngIf="compareAnswer" class="answer-box">
          <p>{{ compareAnswer }}</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .query-row {
      display: flex;
      gap: 1rem;
      margin-top: 1rem;
    }
    .answer-box {
      margin-top: 1.5rem;
      background: rgba(0, 0, 0, 0.4);
      padding: 1.25rem;
      border-radius: 8px;
      line-height: 1.6;
    }
  `]
})
export class RulesComponent {
  activeTab: 'oracle' | 'compare' = 'oracle';
  query = '';
  compareQuery = '';
  oracleAnswer = '';
  compareAnswer = '';

  constructor(private http: HttpClient) {}

  askOracle() {
    if (!this.query.trim()) return;
    this.http.post<any>('http://localhost:8000/api/v1/rules/query', {
      query: this.query,
      edition: '2014 Edition'
    }).subscribe((res) => {
      this.oracleAnswer = res.answer_markdown;
    });
  }

  compareRules() {
    if (!this.compareQuery.trim()) return;
    this.http.post<any>('http://localhost:8000/api/v1/rules/compare', {
      query: this.compareQuery
    }).subscribe((res) => {
      this.compareAnswer = res.comparison_markdown;
    });
  }
}
