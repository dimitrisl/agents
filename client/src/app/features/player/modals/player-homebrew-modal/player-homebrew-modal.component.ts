import { Component, Input, Output, EventEmitter, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HomebrewService, HomebrewItem } from '../../../../core/services/homebrew.service';
import { CharacterStateService } from '../../../../core/services/character-state.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

@Component({
  selector: 'app-player-homebrew-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
  <div class="w-full max-w-3xl bg-surface border border-hairline rounded shadow-xl flex flex-col max-h-[90vh]">
    <!-- Header -->
    <div class="flex items-center justify-between p-4 border-b border-hairline bg-tile">
      <h2 class="text-xl font-bold text-ink flex items-center gap-2">
        <span class="text-gold">🔥</span> Campaign Homebrew
      </h2>
      <button class="text-muted hover:text-ink" (click)="closeModal.emit()">✕</button>
    </div>

    <!-- Body -->
    <div class="p-6 overflow-y-auto space-y-4">
      <div *ngIf="(items$ | async) as items">
        <div *ngIf="items.length === 0" class="text-center py-8 text-muted italic border border-dashed border-hairline rounded">
          No homebrew content available in this campaign.
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div *ngFor="let item of items" class="border border-hairline rounded p-4 bg-surface hover:border-gold/50 transition-colors flex flex-col">
            <div class="flex justify-between items-start mb-2">
              <span class="text-xs font-bold uppercase tracking-wider text-gold px-2 py-1 bg-gold/10 rounded">{{ item.homebrew_type }}</span>
            </div>
            <h3 class="font-bold text-lg text-ink">{{ item.name }}</h3>
            <p class="text-sm text-muted mt-2 mb-4 flex-1">{{ item['description'] || 'No description provided.' }}</p>
            <button
              (click)="equipItem(item._id!)"
              class="w-full mt-auto py-2 rounded font-bold transition-colors bg-gold text-surface hover:bg-gold/90"



              [disabled]="isEquipping"
            >
              Add to Character
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
  `
})
export class PlayerHomebrewModalComponent implements OnInit {
  @Input() campaignName!: string;
  @Input() charId!: string;
  @Output() closeModal = new EventEmitter<void>();

  homebrewService = inject(HomebrewService);
  charState = inject(CharacterStateService);
  toast = inject(RollToastService);

  items$ = this.homebrewService.items$;
  isEquipping = false;

  ngOnInit() {
    this.homebrewService.loadHomebrew(this.campaignName).subscribe();
  }

  equipItem(itemId: string) {
    if (this.isEquipping) return;
    this.isEquipping = true;
    this.charState.addHomebrewToCharacter(this.charId, itemId).subscribe({
      next: () => {
        this.toast.showMessage('✅ ITEM ADDED', 'Homebrew item added to your character sheet.');
        this.isEquipping = false;
        this.closeModal.emit();
      },
      error: (err) => {
        console.error(err);
        this.toast.showMessage('❌ FAILED', 'Could not add the item.');
        this.isEquipping = false;
      }
    });
  }
}
