import { ChangeDetectionStrategy, ChangeDetectorRef, Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import {
  ForgeButtonDirective,
  ForgeModalComponent,
  ForgeInputDirective,
} from '../../../../shared/ui';
import type { PartyMember } from '../../../../core/models/party.model';
import type { HomebrewItem } from '../../../../core/services/homebrew.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import { campaignUrl } from '../../../../core/config/api-urls';

@Component({
  selector: 'app-loot-distribute-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeModalComponent,
    ForgeInputDirective,
  ],
  templateUrl: './loot-distribute-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LootDistributeModalComponent {
  private http = inject(HttpClient);
  private rollToast = inject(RollToastService);
  private cdr = inject(ChangeDetectorRef);

  @Input() open = false;
  @Input() partyMembers: PartyMember[] = [];
  @Input() campaignName = '';
  @Input() homebrewItems: HomebrewItem[] = [];

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() distributed = new EventEmitter<void>();

  selectedCharIds: Record<string, boolean> = {};
  pp = 0;
  gp = 0;
  ep = 0;
  sp = 0;
  cp = 0;
  splitCurrency = false;
  selectedHomebrewId = '';
  customItemName = '';
  customItemDesc = '';
  reason = 'Quest Reward';
  isDistributing = false;

  get availableHomebrewItems(): HomebrewItem[] {
    return this.homebrewItems.filter(
      hb => hb.homebrew_type === 'weapon' || hb.homebrew_type === 'item'
    );
  }

  get allSelected(): boolean {
    if (this.partyMembers.length === 0) return false;
    return this.partyMembers.every(m => m.char_id && this.selectedCharIds[m.char_id]);
  }

  toggleSelectAll(checked: boolean): void {
    this.partyMembers.forEach(m => {
      if (m.char_id) {
        this.selectedCharIds[m.char_id] = checked;
      }
    });
  }

  toggleRecipient(charId: string): void {
    this.selectedCharIds[charId] = !this.selectedCharIds[charId];
  }

  getSelectedIds(): string[] {
    const validIds = new Set(
      this.partyMembers.map(m => m.char_id).filter((id): id is string => !!id)
    );
    return Object.entries(this.selectedCharIds)
      .filter(([id, sel]) => sel && validIds.has(id))
      .map(([id]) => id);
  }

  distribute(): void {
    const characterIds = this.getSelectedIds();
    if (characterIds.length === 0) {
      this.rollToast.showMessage('⚠️ NO RECIPIENTS', 'Select at least one party member to receive loot.');
      return;
    }

    const hasCurrency = this.pp > 0 || this.gp > 0 || this.ep > 0 || this.sp > 0 || this.cp > 0;
    const hasCustomItem = !!this.customItemName.trim();
    const hasHomebrew = !!this.selectedHomebrewId;

    if (!hasCurrency && !hasCustomItem && !hasHomebrew) {
      this.rollToast.showMessage('⚠️ NO LOOT', 'Specify currency or an item to award.');
      return;
    }

    this.isDistributing = true;

    const payload: any = {
      character_ids: characterIds,
      split_currency: this.splitCurrency,
      reason: this.reason || 'Loot Award',
    };

    if (hasCurrency) {
      payload.currency = {
        pp: Number(this.pp) || 0,
        gp: Number(this.gp) || 0,
        ep: Number(this.ep) || 0,
        sp: Number(this.sp) || 0,
        cp: Number(this.cp) || 0,
      };
    }

    const items: any[] = [];
    if (hasCustomItem) {
      items.push({
        name: this.customItemName.trim(),
        description: this.customItemDesc.trim(),
        type: 'item',
      });
    }
    if (items.length > 0) {
      payload.items = items;
    }

    if (hasHomebrew) {
      payload.homebrew_item_ids = [this.selectedHomebrewId];
    }

    const url = campaignUrl(this.campaignName, 'loot/distribute');
    this.http.post<any>(url, payload).subscribe({
      next: (res) => {
        this.isDistributing = false;
        this.rollToast.showMessage('💰 LOOT DISTRIBUTED', res.message || 'Loot awarded successfully!');
        this.distributed.emit();
        this.closeModal();
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.isDistributing = false;
        this.rollToast.showMessage('❌ DISTRIBUTION FAILED', err.error?.detail || 'Failed to distribute loot.');
        this.cdr.markForCheck();
      },
    });
  }

  closeModal(): void {
    this.openChange.emit(false);
    this.closed.emit();
    // Reset form
    this.selectedCharIds = {};
    this.splitCurrency = false;
    this.pp = 0;
    this.gp = 0;
    this.ep = 0;
    this.sp = 0;
    this.cp = 0;
    this.customItemName = '';
    this.customItemDesc = '';
    this.selectedHomebrewId = '';
    this.cdr.markForCheck();
  }
}
