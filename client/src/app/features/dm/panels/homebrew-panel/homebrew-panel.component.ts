import { Component, EventEmitter, Input, OnInit, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
import { BestiaryService } from '../../../../core/services/bestiary.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { AuthService } from '../../../../core/services/auth.service';
import { isReportedGlobally } from '../../../../core/interceptors/error.interceptor';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeConfirmService,
  ForgeEmptyStateComponent,
  ForgeIconComponent,
  ForgeInputDirective,
  ForgeSelectDirective,
  ForgeSpinnerComponent,
} from '../../../../shared/ui';
import { HomebrewForgeModalComponent } from '../../modals/homebrew-forge-modal/homebrew-forge-modal.component';
import type { BestiaryMonster } from '../../../../core/models/bestiary.model';

const MONSTER_TYPES = [
  'all',
  'aberration',
  'beast',
  'celestial',
  'construct',
  'dragon',
  'elemental',
  'fey',
  'fiend',
  'giant',
  'humanoid',
  'monstrosity',
  'ooze',
  'plant',
  'undead',
];

const MONSTER_CRS = [
  'all',
  '0',
  '1/8',
  '1/4',
  '1/2',
  '1',
  '2',
  '3',
  '4',
  '5',
  '6',
  '7',
  '8',
  '9',
  '10',
  '11',
  '12',
  '13',
  '14',
  '15',
  '16',
  '17',
  '18',
  '19',
  '20',
  '21',
  '22',
  '23',
  '24',
];

@Component({
  selector: 'app-homebrew-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeEmptyStateComponent,
    ForgeIconComponent,
    ForgeInputDirective,
    ForgeSelectDirective,
    ForgeSpinnerComponent,
    HomebrewForgeModalComponent,
  ],
  templateUrl: './homebrew-panel.component.html',
  styleUrl: './homebrew-panel.component.css',
})
export class HomebrewPanelComponent implements OnInit {
  @Input() campaignName: string | null = null;
  @Input() edition = 'all';

  @Output() addMonsterToTracker = new EventEmitter<HomebrewItem>();
  @Output() addToInitiative = new EventEmitter<BestiaryMonster>();
  @Output() viewStatblock = new EventEmitter<BestiaryMonster>();

  homebrewService = inject(HomebrewService);
  bestiaryService = inject(BestiaryService);
  private rollToast = inject(RollToastService);
  private confirmDialog = inject(ForgeConfirmService);
  private auth = inject(AuthService);

  items$ = this.homebrewService.items$;
  showForgeModal = false;

  // View state: 'bestiary' is primary, 'campaign' holds custom equipment & spells
  activeView: 'bestiary' | 'campaign' = 'bestiary';

  // Filters for Bestiary Browser
  searchQuery = '';
  editionFilter = 'all';
  crFilter = 'all';
  typeFilter = 'all';
  includeOfficial = true;
  includeMine = true;
  includeCommunity = false;

  readonly monsterTypes = MONSTER_TYPES;
  readonly monsterCrs = MONSTER_CRS;

  // Bestiary signals
  readonly monsters = this.bestiaryService.monsters;
  readonly isLoading = this.bestiaryService.isLoading;

  ngOnInit() {
    if (this.campaignName) {
      this.homebrewService.loadHomebrew(this.campaignName).subscribe();
    }
    if (this.edition && this.edition !== 'all') {
      this.editionFilter = this.edition;
    }
    this.loadBestiary();
  }

  loadBestiary(): void {
    this.bestiaryService
      .getMonsters({
        search: this.searchQuery,
        edition: this.editionFilter,
        cr: this.crFilter,
        monster_type: this.typeFilter,
        include_official: this.includeOfficial,
        include_mine: this.includeMine,
        include_community: this.includeCommunity,
      })
      .subscribe({
        error: (err) => {
          if (!isReportedGlobally(err)) {
            this.rollToast.showMessage('⚠️ LOAD ERROR', err?.error?.detail || 'Failed to load bestiary monsters.');
          }
        },
      });
  }

  toggleSource(source: 'official' | 'mine' | 'community'): void {
    if (source === 'official') {
      this.includeOfficial = !this.includeOfficial;
    } else if (source === 'mine') {
      this.includeMine = !this.includeMine;
    } else if (source === 'community') {
      this.includeCommunity = !this.includeCommunity;
    }
    this.loadBestiary();
  }

  onFilterChange(): void {
    this.loadBestiary();
  }

  isOwner(monster: BestiaryMonster): boolean {
    if (monster.id.startsWith('srd_') || monster.origin === 'official') {
      return false;
    }
    const currentUid = this.auth.currentUser()?.id;
    return monster.origin === 'custom' && (!monster.creator_dm_id || monster.creator_dm_id === currentUid);
  }

  isOfficial(monster: BestiaryMonster): boolean {
    return monster.id.startsWith('srd_') || monster.origin === 'official';
  }

  abilityMod(score?: number): string {
    const s = score ?? 10;
    const mod = Math.floor((s - 10) / 2);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }

  cloneMonster(monster: BestiaryMonster): void {
    this.bestiaryService.cloneMonster(monster.id).subscribe({
      next: (cloned) => {
        this.rollToast.showMessage('📋 MONSTER CLONED', `Created copy: ${cloned.name}`);
      },
      error: (err) => {
        this.rollToast.showMessage('⚠️ CLONE FAILED', err?.error?.detail || 'Could not clone monster.');
      },
    });
  }

  toggleVisibility(monster: BestiaryMonster): void {
    if (this.isOfficial(monster)) return;
    const targetState = !monster.is_public;
    this.bestiaryService.toggleVisibility(monster.id, targetState).subscribe({
      next: (res) => {
        const status = res.is_public ? 'Public' : 'Private';
        this.rollToast.showMessage('🔒 VISIBILITY CHANGED', `${monster.name} is now ${status}.`);
      },
      error: (err) => {
        this.rollToast.showMessage('⚠️ UPDATE FAILED', err?.error?.detail || 'Could not update visibility.');
      },
    });
  }

  async deleteMonster(monster: BestiaryMonster): Promise<void> {
    if (this.isOfficial(monster)) return;
    const confirmed = await this.confirmDialog.ask({
      title: 'Delete monster?',
      message: `Delete "${monster.name}" permanently from your bestiary? This cannot be undone.`,
      confirmLabel: 'Delete monster',
      tone: 'danger',
    });
    if (confirmed) {
      this.bestiaryService.deleteMonster(monster.id).subscribe({
        next: () => {
          this.rollToast.showMessage('🗑️ DELETED', `Deleted ${monster.name} from bestiary.`);
        },
        error: (err) => {
          this.rollToast.showMessage('⚠️ DELETE FAILED', err?.error?.detail || 'Could not delete monster.');
        },
      });
    }
  }

  // --- Campaign Items Deletion (Preserved) ---
  async deleteItem(id: string) {
    if (!this.campaignName) return;
    const confirmed = await this.confirmDialog.ask({
      title: 'Delete homebrew item?',
      message: "It will be removed from this campaign's homebrew. This cannot be undone.",
      confirmLabel: 'Delete item',
      tone: 'danger',
    });
    if (confirmed) {
      this.homebrewService.deleteHomebrew(this.campaignName, id).subscribe({
        error: (err) => {
          if (!isReportedGlobally(err)) {
            this.rollToast.showMessage('⚠️ DELETE FAILED', err?.error?.detail || 'Could not delete the homebrew item.');
          }
        },
      });
    }
  }
}
