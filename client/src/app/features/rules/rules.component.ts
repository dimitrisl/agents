import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { CharacterStateService } from '../../core/services/character-state.service';
import { RollToastService } from '../../core/services/roll-toast.service';
import { environment } from '../../../environments/environment';
import {
  ForgeButtonDirective,
  ForgeCardComponent,
  ForgeInputDirective,
  ForgePageComponent,
  ForgeSectionComponent,
  ForgeTab,
  ForgeTabsComponent,
} from '../../shared/ui';

@Component({
  selector: 'app-rules',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeCardComponent,
    ForgeInputDirective,
    ForgePageComponent,
    ForgeSectionComponent,
    ForgeTabsComponent,
  ],
  templateUrl: './rules.component.html',
  styleUrl: './rules.component.css',
})
export class RulesComponent {
  activeTab: 'oracle' | 'compare' | 'validate' = 'oracle';

  readonly rulesTabs: ForgeTab[] = [
    { id: 'oracle', label: '🔮 Rules Oracle' },
    { id: 'compare', label: '⚖️ 2014 vs 2024 Edition Comparator' },
    { id: 'validate', label: '🛡️ Character Rules Inspector' },
  ];

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
    this.http.post<any>(`${environment.apiBaseUrl}/rules/query`, {
      query: this.oracleQuery,
      edition: this.charState.dndEdition()
    }).subscribe((res) => {
      this.oracleAnswer = res.answer_markdown;
      this.rollToast.showMessage('🔮 ORACLE SEARCH COMPLETE', `Retrieved rules for "${this.oracleQuery}".`);
    });
  }

  compareEditions() {
    if (!this.compareQuery) return;
    this.http.post<any>(`${environment.apiBaseUrl}/rules/compare`, {
      query: this.compareQuery
    }).subscribe((res) => {
      this.compareAnswer = res.comparison_markdown;
      this.rollToast.showMessage('⚖️ EDITION COMPARISON', `Compared 2014 vs 2024 rules for "${this.compareQuery}".`);
    });
  }

  validateActiveHero() {
    const char = this.charState.activeCharacter();
    if (!char) return;
    this.http.post<any>(`${environment.apiBaseUrl}/rules/validate`, {
      character: char
    }).subscribe((res) => {
      this.validationResult = res.validation_result;
      const statusText = res.validation_result?.valid ? 'PASSED' : 'DISCREPANCIES DETECTED';
      this.rollToast.showMessage('🛡️ BUILD AUDIT COMPLETE', `Audit status for ${char.char_name}: ${statusText}`);
    });
  }
}
