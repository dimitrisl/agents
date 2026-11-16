import { Component, DestroyRef, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { CommonModule } from '@angular/common';
import { map } from 'rxjs';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
import { CharacterStateService } from '../../../../core/services/character-state.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';

@Component({
  selector: 'app-player-homebrew-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  template: `
<forge-modal [open]="true" (closed)="closeModal.emit()" title="🔥 Campaign Homebrew" maxWidth="768px">
  <div *ngIf="(items$ | async) as items">
    <div *ngIf="items.length === 0" class="text-center py-8 text-muted italic border border-dashed border-hairline rounded">
      No homebrew content available in this campaign.
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div *ngFor="let item of items" class="border border-hairline rounded-lg p-4 bg-panel hover:border-gold/50 transition-colors flex flex-col">
        <div class="flex justify-between items-start mb-2">
          <span class="text-xs font-bold uppercase tracking-wider text-gold px-2 py-1 bg-gold/10 rounded">{{ item.homebrew_type }}</span>
        </div>
        <h3 class="font-bold text-lg text-ink">{{ item.name }}</h3>
        <p class="text-sm text-muted mt-2 mb-4 flex-1">{{ item['description'] || 'No description provided.' }}</p>
        <button
          forgeButton
          variant="secondary"
          tone="accent"
          type="button"
          (click)="equipItem(item._id!)"
          class="w-full mt-auto"
          [loading]="equippingItemId === item._id"
          [disabled]="isEquipping"
        >
          Add to Character
        </button>
      </div>
    </div>
  </div>
</forge-modal>
  `
})
export class PlayerHomebrewModalComponent implements OnInit {
  @Input() campaignName!: string;
  @Input() charId!: string;
  @Output() closeModal = new EventEmitter<void>();

  homebrewService = inject(HomebrewService);
  charState = inject(CharacterStateService);
  toast = inject(RollToastService);
  private readonly destroyRef = inject(DestroyRef);

  items$ = this.homebrewService.items$.pipe(
    map(items => items.filter(item => item.homebrew_type !== 'monster'))
  );
  isEquipping = false;
  equippingItemId: string | null = null;

  ngOnInit() {
    this.homebrewService.loadHomebrew(this.campaignName).pipe(takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  equipItem(itemId: string) {
    if (this.isEquipping) return;
    this.isEquipping = true;
    this.equippingItemId = itemId;
    this.charState.addHomebrewToCharacter(this.charId, itemId)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
      next: () => {
        this.toast.showMessage('✅ ITEM ADDED', 'Homebrew item added to your character sheet.');
        this.isEquipping = false;
        this.equippingItemId = null;
        this.closeModal.emit();
      },
      error: (err) => {
        console.error(err);
        this.toast.showMessage('❌ FAILED', 'Could not add the item.');
        this.isEquipping = false;
        this.equippingItemId = null;
      }
    });
  }
}
