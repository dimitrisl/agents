import { Component, Input, OnInit, effect, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CdkDragEnd, DragDropModule } from '@angular/cdk/drag-drop';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTState, VTTToken } from '../../../core/models/vtt.model';
import { InitiativeCombatant } from '../../../core/models/initiative.model';
import { FormsModule } from '@angular/forms';
import { ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeSelectDirective } from '../../../shared/ui';

@Component({
  selector: 'app-vtt-grid',
  standalone: true,
  imports: [CommonModule, DragDropModule, FormsModule, ForgeButtonDirective, ForgeInputDirective, ForgeModalComponent, ForgeSelectDirective],
  template: `
    <div class="vtt-container" *ngIf="vttState()?.is_active" [class.minimized]="isMinimized">
      <!-- Controls -->
      <div class="vtt-controls bg-panel border-b border-hairline p-2 flex gap-2 justify-between items-center z-10 relative">
        <div class="flex gap-4 items-center">
          <h3 class="text-ink font-bold tracking-wider">VTT Grid</h3>
          <ng-container *ngIf="role === 'dm'">
            <div class="flex items-center gap-2">
              <select #combatantSelect forgeSelect>
                <option value="">-- Select Combatant --</option>
                <option *ngFor="let c of combatants" [value]="c.id">{{ c.name }}</option>
              </select>
              <button forgeButton variant="primary" size="sm" (click)="addCombatantToken(combatantSelect.value)">Add Token</button>
            </div>
            <button forgeButton variant="secondary" size="sm" (click)="changeBackground()">Set Map</button>
          </ng-container>
        </div>
        <div class="flex gap-2">
          <button forgeButton variant="secondary" size="sm" (click)="toggleMinimize()">
            {{ isMinimized ? 'Expand' : 'Minimize' }}
          </button>
          <button *ngIf="role === 'dm'" forgeButton variant="danger" size="sm" (click)="closeGrid()">Close Grid</button>
        </div>
      </div>

      <!-- The Grid Canvas -->
      <div class="vtt-canvas" *ngIf="!isMinimized" [style.backgroundImage]="vttState()?.grid?.background_image_url ? 'url(' + vttState()!.grid!.background_image_url + ')' : 'none'">
        <div class="grid-overlay"
             [style.backgroundSize]="(vttState()?.grid?.cell_size || 50) + 'px ' + (vttState()?.grid?.cell_size || 50) + 'px'">
        </div>

        <!-- Tokens -->
        <div *ngFor="let token of vttState()?.tokens"
             class="vtt-token"
             [class.hidden-token]="token.is_hidden && role !== 'dm'"
             [style.opacity]="token.is_hidden ? 0.5 : 1"
             [style.width.px]="getTokenDimension(token)"
             [style.height.px]="getTokenDimension(token)"
             cdkDrag
             [cdkDragFreeDragPosition]="{x: token.x, y: token.y}"
             (cdkDragEnded)="onDragEnded($event, token)"
             [cdkDragDisabled]="!canMoveToken(token)">

          <img *ngIf="token.image_url" [src]="token.image_url" class="token-img"
               [style.width.px]="getTokenInnerDimension(token)"
               [style.height.px]="getTokenInnerDimension(token)"
               [class.enemy-border]="token.is_enemy" [class.player-border]="!token.is_enemy">
          <div *ngIf="!token.image_url" class="token-fallback"
               [style.width.px]="getTokenInnerDimension(token)"
               [style.height.px]="getTokenInnerDimension(token)"
               [style.fontSize.px]="getTokenFontSize(token)"
               [class.enemy-fallback]="token.is_enemy" [class.player-fallback]="!token.is_enemy">
            {{ token.name.charAt(0) }}
          </div>

          <div class="token-label">
            {{ token.name }}
            <span *ngIf="getTokenScale(token) > 1" class="text-[9px] opacity-75">({{ getTokenScale(token) }}x{{ getTokenScale(token) }})</span>
          </div>

          <div *ngIf="role === 'dm'" class="token-actions">
            <button (click)="cycleTokenSize(token, $event)" class="size-token-btn" title="Cycle Size (Medium/Large/Huge/Gargantuan)" aria-label="Cycle token size">
              {{ getTokenScale(token) }}x
            </button>
            <button (click)="removeToken(token.id)" class="remove-token-btn" title="Remove Token" aria-label="Remove token">×</button>
          </div>

          <div class="token-hp-bar" *ngIf="token.max_hp && token.hp !== undefined && (role === 'dm' || !token.is_enemy)"
               [style.width.px]="getTokenInnerDimension(token)"
               role="meter" aria-label="Hit points" aria-valuemin="0" [attr.aria-valuemax]="token.max_hp" [attr.aria-valuenow]="token.hp">
            <div class="hp-fill" [style.width.%]="(token.hp / token.max_hp) * 100"></div>
          </div>
        </div>
      </div>

      <!-- Map Background Modal -->
      <forge-modal
        [open]="showMapModal"
        (openChange)="showMapModal = $event"
        title="Configure VTT Map"
        maxWidth="480px">
        <div class="flex flex-col gap-4 p-4">
          <div>
            <label class="block text-label font-semibold text-muted mb-1">Map Image URL</label>
            <input
              forgeInput
              type="text"
              placeholder="https://..."
              [(ngModel)]="mapUrlInput"
              class="w-full text-body"
            />
          </div>
          <div>
            <label class="block text-label font-semibold text-muted mb-1">Grid Cell Size (px)</label>
            <input
              forgeInput
              type="number"
              min="20"
              max="200"
              [(ngModel)]="gridSizeInput"
              class="w-32 text-body"
            />
          </div>
          <div class="flex justify-end gap-2 mt-4">
            <button forgeButton variant="secondary" size="sm" type="button" (click)="showMapModal = false">Cancel</button>
            <button forgeButton variant="primary" size="sm" type="button" (click)="applyMapBackground()">Apply Map</button>
          </div>
        </div>
      </forge-modal>
    </div>
  `,
  styles: [`
    .vtt-container {
      width: 100%;
      height: 600px;
      background: var(--color-deep);
      border: 1px solid var(--color-hairline);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      margin-top: 24px;
      transition: height 0.3s ease;
    }
    @media (prefers-reduced-motion: reduce) {
      .vtt-container { transition: none; }
    }
    .vtt-container.minimized {
      height: 48px;
    }
    .vtt-controls {
      min-height: 48px;
      box-sizing: border-box;
      flex-wrap: wrap;
    }
    .vtt-canvas {
      flex: 1;
      position: relative;
      overflow: auto;
      background-color: var(--color-deep);
      background-repeat: no-repeat;
      background-position: top left;
      background-attachment: local;
    }
    .grid-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      pointer-events: none;
      background-image: linear-gradient(to right, color-mix(in srgb, var(--color-ink) 10%, transparent) 1px, transparent 1px),
                        linear-gradient(to bottom, color-mix(in srgb, var(--color-ink) 10%, transparent) 1px, transparent 1px);
      min-width: 2000px;
      min-height: 2000px;
    }
    .vtt-token {
      position: absolute;
      cursor: grab;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
    }
    .vtt-token:active { cursor: grabbing; }
    .hidden-token { display: none !important; }

    .token-img {
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid;
    }
    .enemy-border { border-color: var(--color-red); }
    .player-border { border-color: var(--color-cobalt); }

    .token-fallback {
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: var(--color-ink); font-weight: bold;
      border: 2px solid var(--color-hairline-hover);
    }
    .enemy-fallback { background: color-mix(in srgb, var(--color-red) 35%, var(--color-surface)); }
    .player-fallback { background: color-mix(in srgb, var(--color-cobalt) 35%, var(--color-surface)); }

    .token-label {
      position: absolute;
      bottom: -15px;
      background: color-mix(in srgb, var(--color-surface) 85%, transparent);
      color: var(--color-ink);
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 4px;
      white-space: nowrap;
      pointer-events: none;
    }

    .token-actions {
      position: absolute;
      top: -12px;
      right: -12px;
      display: none;
      align-items: center;
      gap: 3px;
      z-index: 20;
    }
    .vtt-token:hover .token-actions,
    .vtt-token:focus-within .token-actions {
      display: flex;
    }

    .size-token-btn {
      background: var(--color-surface);
      color: var(--color-accent);
      border: 1px solid var(--color-accent);
      border-radius: 4px;
      padding: 0 4px;
      height: 22px;
      font-size: 10px;
      font-weight: bold;
      cursor: pointer;
    }
    .size-token-btn:focus-visible {
      outline: 2px solid var(--color-accent);
    }

    .remove-token-btn {
      background: var(--color-surface);
      color: var(--color-red);
      border: 1px solid var(--color-red);
      border-radius: 50%;
      width: 22px; height: 22px;
      font-size: 14px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
    }
    .remove-token-btn:focus-visible {
      outline: 2px solid var(--color-accent);
      outline-offset: 2px;
    }

    .token-hp-bar {
      position: absolute;
      top: -5px;
      width: 40px;
      height: 4px;
      background: var(--color-surface);
      border-radius: 2px;
      overflow: hidden;
    }
    .hp-fill {
      height: 100%;
      background: var(--color-emerald);
    }
  `]
})
export class VttGridComponent implements OnInit {
  @Input() role: 'dm' | 'player' = 'player';
  @Input() characterName?: string;
  @Input() combatants: InitiativeCombatant[] = [];

  wsService = inject(WebSocketService);
  readonly vttState = this.wsService.vttState;
  isMinimized: boolean = false;
  showMapModal: boolean = false;
  mapUrlInput: string = '';
  gridSizeInput: number = 50;

  constructor() {}

  ngOnInit(): void {}

  toggleMinimize(): void {
    this.isMinimized = !this.isMinimized;
  }

  canMoveToken(token: VTTToken): boolean {
    if (this.role === 'dm') return true;
    if (this.characterName && token.name.toLowerCase() === this.characterName.toLowerCase()) return true;
    return false;
  }

  onDragEnded(event: CdkDragEnd, token: VTTToken): void {
    const position = event.source.getFreeDragPosition();
    const state = this.vttState();
    // Snap to grid (cell_size)
    const cellSize = state?.grid?.cell_size || 50;
    const snappedX = Math.round(position.x / cellSize) * cellSize;
    const snappedY = Math.round(position.y / cellSize) * cellSize;

    // Update local immediately for responsiveness
    event.source.setFreeDragPosition({x: snappedX, y: snappedY});
    token.x = snappedX;
    token.y = snappedY;

    // Broadcast
    this.wsService.sendVttMove(token.id, snappedX, snappedY);
  }

  closeGrid(): void {
    if (this.role === 'dm') {
      this.wsService.sendVttToggle(false);
    }
  }

  parseCreatureSize(rawSize: any): number {
    if (typeof rawSize === 'number' && rawSize >= 1) {
      return Math.min(6, Math.floor(rawSize));
    }
    if (typeof rawSize === 'string') {
      const lower = rawSize.toLowerCase().trim();
      if (lower.includes('gargantuan')) return 4;
      if (lower.includes('huge')) return 3;
      if (lower.includes('large')) return 2;
    }
    return 1;
  }

  getTokenScale(token: VTTToken): number {
    const s = Number(token?.size);
    return Number.isFinite(s) && s >= 1 ? s : 1;
  }

  getTokenDimension(token: VTTToken): number {
    const cellSize = this.vttState()?.grid?.cell_size || 50;
    return cellSize * this.getTokenScale(token);
  }

  getTokenInnerDimension(token: VTTToken): number {
    const dim = this.getTokenDimension(token);
    return Math.max(30, dim - 10);
  }

  getTokenFontSize(token: VTTToken): number {
    const scale = this.getTokenScale(token);
    return Math.max(16, 14 * scale);
  }

  cycleTokenSize(token: VTTToken, event: MouseEvent): void {
    event.stopPropagation();
    if (this.role !== 'dm') return;
    const current = this.getTokenScale(token);
    const nextSize = current >= 4 ? 1 : current + 1;
    const updated = { ...token, size: nextSize };
    this.wsService.vttState.update((s) => {
      if (!s) return s;
      return {
        ...s,
        tokens: s.tokens.map((t) => (t.id === token.id ? updated : t)),
      };
    });
    this.wsService.sendVttAddToken(updated);
  }

  addCombatantToken(combatantId: string) {
    if (!combatantId) return;
    const combatant = this.combatants.find(c => c.id === combatantId);
    if (!combatant) return;

    const state = this.vttState();
    // Check if token already exists to avoid duplicates
    if (state?.tokens?.some((t: VTTToken) => t.id === combatant.id)) {
      return;
    }

    let tokenName = combatant.name;
    const existingTokens = state?.tokens || [];
    const sameNameTokens = existingTokens.filter(t =>
      t.name.toLowerCase() === combatant.name.toLowerCase() ||
      new RegExp(`^${combatant.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*#\\d+$`, 'i').test(t.name)
    );
    if (sameNameTokens.length > 0 && !/(\s+\d+|\s*#\d+)$/.test(combatant.name)) {
      tokenName = `${combatant.name} #${sameNameTokens.length + 1}`;
    }

    const token: VTTToken = {
      id: combatant.id,
      name: tokenName,
      x: 100 + Math.floor(Math.random() * 50),
      y: 100 + Math.floor(Math.random() * 50),
      size: this.parseCreatureSize(combatant.size || (combatant as any).creature_size),
      is_enemy: !combatant.is_player,
      is_hidden: false,
      hp: combatant.hp,
      max_hp: combatant.max_hp,
      image_url: combatant.portrait || ''
    };

    // Optimistic update
    this.wsService.vttState.update(s => {
      if (!s) return s;
      return { ...s, tokens: [...s.tokens, token] };
    });

    this.wsService.sendVttAddToken(token);
  }

  removeToken(tokenId: string) {
    // Optimistic update
    this.wsService.vttState.update(s => {
      if (!s) return s;
      return { ...s, tokens: s.tokens.filter(t => t.id !== tokenId) };
    });
    this.wsService.sendVttRemoveToken(tokenId);
  }

  changeBackground() {
    this.mapUrlInput = this.vttState()?.grid?.background_image_url || 'https://i.imgur.com/G4hXqD7.jpg';
    this.gridSizeInput = this.vttState()?.grid?.cell_size || 50;
    this.showMapModal = true;
  }

  applyMapBackground() {
    const url = this.mapUrlInput.trim();
    const cellSize = Math.max(20, Math.min(200, Number(this.gridSizeInput) || 50));
    if (url) {
      // Optimistic update
      this.wsService.vttState.update(s => {
        if (!s) return s;
        return { ...s, grid: { ...s.grid, background_image_url: url, cell_size: cellSize } };
      });
      this.wsService.sendVttUpdateGrid({ background_image_url: url, cell_size: cellSize });
    }
    this.showMapModal = false;
  }
}
