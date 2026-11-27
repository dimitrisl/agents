import {
  ChangeDetectionStrategy,
  ChangeDetectorRef,
  Component,
  DestroyRef,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  inject,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
  ForgeSpinnerComponent,
  ForgeToggleComponent,
} from '../../../../shared/ui';
import type { LootCoinKey, LootItemSource, OfficialLootItem } from '../../../../core/models/loot.model';
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
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
    ForgeSpinnerComponent,
    ForgeToggleComponent,
  ],
  templateUrl: './loot-distribute-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LootDistributeModalComponent implements OnChanges {
  private http = inject(HttpClient);
  private rollToast = inject(RollToastService);
  private cdr = inject(ChangeDetectorRef);
  private destroyRef = inject(DestroyRef);

  @Input() open = false;
  @Input() partyMembers: PartyMember[] = [];
  @Input() campaignName = '';
  @Input() homebrewItems: HomebrewItem[] = [];
  @Input() officialItems: OfficialLootItem[] = [];
  @Input() loadingOfficialItems = false;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() distributed = new EventEmitter<void>();
  @Output() requestOfficialItems = new EventEmitter<void>();

  readonly coinDefs: ReadonlyArray<{ key: LootCoinKey; label: string; colorClass: string }> = [
    { key: 'pp', label: 'PP', colorClass: 'text-ink' },
    { key: 'gp', label: 'GP', colorClass: 'text-gold' },
    { key: 'ep', label: 'EP', colorClass: 'text-cobalt' },
    { key: 'sp', label: 'SP', colorClass: 'text-muted' },
    { key: 'cp', label: 'CP', colorClass: 'text-gold/80' },
  ];

  selectedCharIds: Record<string, boolean> = {};
  pp = 0;
  gp = 0;
  ep = 0;
  sp = 0;
  cp = 0;
  splitCurrency = false;

  itemSource: LootItemSource = 'custom';
  readonly itemSourceOrder: ReadonlyArray<LootItemSource> = ['custom', 'official', 'homebrew'];
  selectedHomebrewId = '';
  selectedOfficialItemName = '';
  officialItemSearch = '';
  officialItemQuantity = 1;
  officialItemQuantityInput = '1';
  customItemName = '';
  customItemDesc = '';
  customItemQuantity = 1;
  customItemQuantityInput = '1';
  itemRecipientId = '';
  reason = 'Quest Reward';
  isDistributing = false;

  private didCloseForCurrentOpen = false;
  private openSession = 0;
  private activeDistributeSession: number | null = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open'] && this.open) {
      this.openSession += 1;
      this.didCloseForCurrentOpen = false;
      this.isDistributing = false;
      this.activeDistributeSession = null;
    }
    if (changes['partyMembers']) {
      const validIds = new Set(this.targetableMembers.map((m) => m.char_id!));
      const next: Record<string, boolean> = {};
      for (const [id, sel] of Object.entries(this.selectedCharIds)) {
        if (sel && validIds.has(id)) {
          next[id] = true;
        }
      }
      this.selectedCharIds = next;
      if (this.itemRecipientId && !next[this.itemRecipientId]) {
        this.itemRecipientId = '';
      }
    }
  }

  get targetableMembers(): PartyMember[] {
    return (this.partyMembers || []).filter((m) => !!m.char_id);
  }

  get unlinkedMembers(): PartyMember[] {
    return (this.partyMembers || []).filter((m) => !m.char_id);
  }

  get selectedPartyMembers(): PartyMember[] {
    return this.targetableMembers.filter((m) => this.selectedCharIds[m.char_id!]);
  }

  get availableHomebrewItems(): HomebrewItem[] {
    return (this.homebrewItems || []).filter(
      (hb) => hb.homebrew_type === 'weapon' || hb.homebrew_type === 'item'
    );
  }

  get filteredOfficialItems(): OfficialLootItem[] {
    const query = this.officialItemSearch.trim().toLowerCase();
    const list = this.officialItems || [];
    if (!query) return list;
    return list.filter(
      (item) =>
        item.name.toLowerCase().includes(query) ||
        (item.type || '').toLowerCase().includes(query) ||
        (item.rarity || '').toLowerCase().includes(query)
    );
  }

  get selectedOfficialItem(): OfficialLootItem | null {
    if (!this.selectedOfficialItemName) return null;
    return (this.officialItems || []).find((i) => i.name === this.selectedOfficialItemName) ?? null;
  }

  get allSelected(): boolean {
    const members = this.targetableMembers;
    if (members.length === 0) return false;
    return members.every((m) => !!this.selectedCharIds[m.char_id!]);
  }

  get hasPositiveCurrency(): boolean {
    return (
      this.safeCoin(this.pp) > 0 ||
      this.safeCoin(this.gp) > 0 ||
      this.safeCoin(this.ep) > 0 ||
      this.safeCoin(this.sp) > 0 ||
      this.safeCoin(this.cp) > 0
    );
  }

  get hasAnyItem(): boolean {
    return (
      !!this.customItemName.trim() ||
      !!this.selectedHomebrewId ||
      !!this.selectedOfficialItem
    );
  }

  get canDistribute(): boolean {
    return !this.isDistributing && this.getSelectedIds().length > 0 && (this.hasPositiveCurrency || this.hasAnyItem);
  }

  get splitPreviewText(): string {
    const divisor = this.getSelectedIds().length;
    if (!this.splitCurrency || divisor <= 1 || !this.hasPositiveCurrency) return '';

    const rawPp = this.safeCoin(this.pp);
    const rawGp = this.safeCoin(this.gp);
    const rawEp = this.safeCoin(this.ep);
    const rawSp = this.safeCoin(this.sp);
    const rawCp = this.safeCoin(this.cp);

    const ppEach = Math.floor(rawPp / divisor);
    const ppRem = rawPp % divisor;
    const gpTotal = rawGp + ppRem * 10;
    const gpEach = Math.floor(gpTotal / divisor);
    const gpRem = gpTotal % divisor;
    const epEach = Math.floor(rawEp / divisor);
    const epRem = rawEp % divisor;
    const spTotal = rawSp + gpRem * 10 + epRem * 5;
    const spEach = Math.floor(spTotal / divisor);
    const spRem = spTotal % divisor;
    const cpTotal = rawCp + spRem * 10;
    const cpEach = Math.floor(cpTotal / divisor);
    const leftoverCp = cpTotal % divisor;

    const parts: string[] = [];
    if (ppEach) parts.push(`${ppEach} pp`);
    if (gpEach) parts.push(`${gpEach} gp`);
    if (epEach) parts.push(`${epEach} ep`);
    if (spEach) parts.push(`${spEach} sp`);
    if (cpEach) parts.push(`${cpEach} cp`);

    const base = parts.length ? parts.join(', ') : '0 cp';
    return leftoverCp > 0
      ? `Each hero gets ${base} (+1 cp remainder to first ${leftoverCp === 1 ? 'hero' : `${leftoverCp} heroes`})`
      : `Each hero gets ${base}`;
  }

  setItemSource(source: LootItemSource): void {
    if (this.itemSource === source) return;
    this.itemSource = source;
    // Enforce mutually exclusive radiogroup semantics so hidden tabs cannot silently award items
    if (source !== 'custom') {
      this.customItemName = '';
      this.customItemDesc = '';
      this.customItemQuantity = 1;
      this.customItemQuantityInput = '1';
    }
    if (source !== 'official') {
      this.selectedOfficialItemName = '';
      this.officialItemSearch = '';
      this.officialItemQuantity = 1;
      this.officialItemQuantityInput = '1';
    }
    if (source !== 'homebrew') {
      this.selectedHomebrewId = '';
    }
    if (source === 'official' && this.officialItems.length === 0 && !this.loadingOfficialItems) {
      this.requestOfficialItems.emit();
    }
  }

  onItemSourceKeydown(event: KeyboardEvent): void {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    event.preventDefault();
    const idx = this.itemSourceOrder.indexOf(this.itemSource);
    const delta = event.key === 'ArrowRight' ? 1 : -1;
    const nextIdx = (idx + delta + this.itemSourceOrder.length) % this.itemSourceOrder.length;
    const nextSource = this.itemSourceOrder[nextIdx];
    this.setItemSource(nextSource);
    const group = (event.currentTarget as HTMLElement | null)?.closest('[role="radiogroup"]');
    const nextBtn = group?.querySelector<HTMLButtonElement>(`[data-testid="loot-source-${nextSource}"]`);
    nextBtn?.focus();
  }

  onOfficialSearchChange(query: string): void {
    this.officialItemSearch = query;
    if (
      this.selectedOfficialItemName &&
      !this.filteredOfficialItems.some((item) => item.name === this.selectedOfficialItemName)
    ) {
      this.selectedOfficialItemName = '';
    }
  }

  coinDisplay(coin: LootCoinKey): string {
    const val = this.safeCoin(this[coin]);
    return val > 0 ? String(val) : '';
  }

  onCoinInput(coin: LootCoinKey, rawOrEvent: Event | string | number | null | undefined): void {
    const inputEl =
      rawOrEvent && typeof rawOrEvent === 'object' && 'target' in rawOrEvent
        ? (rawOrEvent.target as HTMLInputElement | null)
        : null;
    const raw = inputEl ? inputEl.value : rawOrEvent;
    const digits = String(raw ?? '').replace(/[^0-9]/g, '');
    const parsed = digits ? Math.min(9999999, parseInt(digits, 10)) : 0;
    this[coin] = parsed;
    if (inputEl) {
      const display = parsed > 0 ? String(parsed) : '';
      if (inputEl.value !== display) {
        inputEl.value = display;
      }
    }
  }

  onQuantityInput(
    rawOrEvent: Event | string | number | null | undefined,
    target: 'custom' | 'official' = 'custom'
  ): void {
    const inputEl =
      rawOrEvent && typeof rawOrEvent === 'object' && 'target' in rawOrEvent
        ? (rawOrEvent.target as HTMLInputElement | null)
        : null;
    const raw = inputEl ? inputEl.value : rawOrEvent;
    const digits = String(raw ?? '')
      .replace(/[^0-9]/g, '')
      .replace(/^0+/, '');
    if (!digits) {
      if (target === 'official') {
        this.officialItemQuantity = 1;
        this.officialItemQuantityInput = '';
      } else {
        this.customItemQuantity = 1;
        this.customItemQuantityInput = '';
      }
      if (inputEl && inputEl.value !== '') {
        inputEl.value = '';
      }
      return;
    }
    const parsed = Math.max(1, Math.min(999, parseInt(digits, 10) || 1));
    const display = String(parsed);
    if (target === 'official') {
      this.officialItemQuantity = parsed;
      this.officialItemQuantityInput = display;
    } else {
      this.customItemQuantity = parsed;
      this.customItemQuantityInput = display;
    }
    if (inputEl && inputEl.value !== display) {
      inputEl.value = display;
    }
  }

  onQuantityBlur(target: 'custom' | 'official' = 'custom'): void {
    if (target === 'official') {
      this.officialItemQuantityInput = String(this.officialItemQuantity);
    } else {
      this.customItemQuantityInput = String(this.customItemQuantity);
    }
  }

  toggleSelectAll(checked: boolean): void {
    const next = { ...this.selectedCharIds };
    this.targetableMembers.forEach((m) => {
      next[m.char_id!] = checked;
    });
    this.selectedCharIds = next;
    if (!checked) {
      this.itemRecipientId = '';
    }
  }

  toggleRecipient(charId: string): void {
    if (!charId) return;
    const nextVal = !this.selectedCharIds[charId];
    this.selectedCharIds = {
      ...this.selectedCharIds,
      [charId]: nextVal,
    };
    if (!nextVal && this.itemRecipientId === charId) {
      this.itemRecipientId = '';
    }
  }

  getSelectedIds(): string[] {
    return this.selectedPartyMembers.map((m) => m.char_id!);
  }

  distribute(): void {
    if (this.isDistributing) return;

    const characterIds = this.getSelectedIds();
    if (characterIds.length === 0) {
      this.rollToast.showMessage('⚠️ NO RECIPIENTS', 'Select at least one party member to receive loot.');
      return;
    }

    const currency = {
      pp: this.safeCoin(this.pp),
      gp: this.safeCoin(this.gp),
      ep: this.safeCoin(this.ep),
      sp: this.safeCoin(this.sp),
      cp: this.safeCoin(this.cp),
    };
    const hasCurrency =
      currency.pp > 0 || currency.gp > 0 || currency.ep > 0 || currency.sp > 0 || currency.cp > 0;
    const hasCustomItem = !!this.customItemName.trim();
    const officialItem = this.selectedOfficialItem;
    const hasOfficialItem = !!officialItem;
    const hasHomebrew = !!this.selectedHomebrewId;

    if (!hasCurrency && !hasCustomItem && !hasOfficialItem && !hasHomebrew) {
      this.rollToast.showMessage('⚠️ NO LOOT', 'Specify currency or an item to award.');
      return;
    }

    this.isDistributing = true;
    const session = this.openSession;
    const submittedCampaign = this.campaignName;
    this.activeDistributeSession = session;

    const payload: any = {
      character_ids: characterIds,
      split_currency: this.splitCurrency,
      reason: this.reason.trim() || 'Loot Award',
    };

    if (hasCurrency) {
      payload.currency = currency;
    }

    const items: any[] = [];
    if (hasCustomItem) {
      const customEntry: any = {
        name: this.customItemName.trim(),
        description: this.customItemDesc.trim(),
        type: 'item',
      };
      const qty = Math.max(1, Math.floor(Number(this.customItemQuantity) || 1));
      if (qty > 1) {
        customEntry.quantity = qty;
      }
      items.push(customEntry);
    }
    if (officialItem) {
      // Intentionally omit `ac_bonus` so backend `stats_service.py` resolves base + magic bonus
      // (e.g. Shield +1/+2/+3) and Athas suppression authoritatively from RulesRepository by name.
      const offEntry: any = {
        name: officialItem.name,
        description: officialItem.description || '',
        type: 'item',
      };
      const qty = Math.max(1, Math.floor(Number(this.officialItemQuantity) || 1));
      if (qty > 1) {
        offEntry.quantity = qty;
      }
      if (officialItem.weight !== undefined && officialItem.weight !== null) {
        offEntry.weight = officialItem.weight;
      }
      if (officialItem.requires_attunement) {
        offEntry.requires_attunement = true;
      }
      items.push(offEntry);
    }
    if (items.length > 0) {
      payload.items = items;
    }

    if (hasHomebrew) {
      payload.homebrew_item_ids = [this.selectedHomebrewId];
    }

    if (
      (hasCustomItem || hasOfficialItem || hasHomebrew) &&
      characterIds.length > 1 &&
      this.itemRecipientId &&
      characterIds.includes(this.itemRecipientId)
    ) {
      payload.item_recipient_id = this.itemRecipientId;
    }

    const url = campaignUrl(submittedCampaign, 'loot/distribute');
    this.http
      .post<any>(url, payload)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (res) => {
          if (this.activeDistributeSession === session) {
            this.isDistributing = false;
            this.activeDistributeSession = null;
          }
          this.rollToast.showMessage('💰 LOOT DISTRIBUTED', res.message || 'Loot awarded successfully!');
          if (this.campaignName === submittedCampaign) {
            this.distributed.emit();
          }
          if (this.openSession === session && !this.didCloseForCurrentOpen) {
            this.closeModal();
          }
          this.cdr.markForCheck();
        },
        error: (err) => {
          if (this.activeDistributeSession === session) {
            this.isDistributing = false;
            this.activeDistributeSession = null;
          }
          if (this.campaignName === submittedCampaign) {
            this.rollToast.showMessage(
              '❌ DISTRIBUTION FAILED',
              this.formatApiError(err, 'Failed to distribute loot.')
            );
          }
          this.cdr.markForCheck();
        },
      });
  }

  onModalClosed(): void {
    if (this.didCloseForCurrentOpen) return;
    this.didCloseForCurrentOpen = true;
    this.resetForm();
    this.openChange.emit(false);
    this.closed.emit();
    this.cdr.markForCheck();
  }

  closeModal(): void {
    this.didCloseForCurrentOpen = true;
    this.resetForm();
    this.openChange.emit(false);
    this.closed.emit();
    this.cdr.markForCheck();
  }

  private resetForm(): void {
    this.selectedCharIds = {};
    this.splitCurrency = false;
    this.pp = 0;
    this.gp = 0;
    this.ep = 0;
    this.sp = 0;
    this.cp = 0;
    this.itemSource = 'custom';
    this.customItemName = '';
    this.customItemDesc = '';
    this.customItemQuantity = 1;
    this.customItemQuantityInput = '1';
    this.selectedHomebrewId = '';
    this.selectedOfficialItemName = '';
    this.officialItemSearch = '';
    this.officialItemQuantity = 1;
    this.officialItemQuantityInput = '1';
    this.itemRecipientId = '';
    this.reason = 'Quest Reward';
  }

  private safeCoin(val: number | string | null | undefined): number {
    const n = Number(val);
    if (!Number.isFinite(n) || n <= 0) return 0;
    return Math.floor(n);
  }

  private formatApiError(err: any, fallback: string): string {
    const detail = err?.error?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      const msgs = detail
        .map((item) => (typeof item === 'string' ? item : item?.msg || ''))
        .filter((m) => !!m.trim());
      if (msgs.length > 0) return msgs.join(' · ');
    }
    return fallback;
  }
}
