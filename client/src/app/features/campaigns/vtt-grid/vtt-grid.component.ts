import { Component, Input, OnInit, effect, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CdkDragEnd, DragDropModule } from '@angular/cdk/drag-drop';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTState, VTTToken } from '../../../core/models/vtt.model';
import { InitiativeCombatant } from '../../../core/models/initiative.model';
import { ForgeButtonDirective, ForgeSelectDirective } from '../../../shared/ui';

@Component({
  selector: 'app-vtt-grid',
  standalone: true,
  imports: [CommonModule, DragDropModule, ForgeButtonDirective, ForgeSelectDirective],
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
             cdkDrag
             [cdkDragFreeDragPosition]="{x: token.x, y: token.y}"
             (cdkDragEnded)="onDragEnded($event, token)"
             [cdkDragDisabled]="!canMoveToken(token)">

          <img *ngIf="token.image_url" [src]="token.image_url" class="token-img" [class.enemy-border]="token.is_enemy" [class.player-border]="!token.is_enemy">
          <div *ngIf="!token.image_url" class="token-fallback" [class.enemy-fallback]="token.is_enemy" [class.player-fallback]="!token.is_enemy">
            {{ token.name.charAt(0) }}
          </div>

          <div class="token-label">{{ token.name }}</div>

          <button *ngIf="role === 'dm'" (click)="removeToken(token.id)" class="remove-token-btn" title="Remove Token" aria-label="Remove token">×</button>

          <div class="token-hp-bar" *ngIf="token.max_hp && token.hp !== undefined && (role === 'dm' || !token.is_enemy)"
               role="meter" aria-label="Hit points" aria-valuemin="0" [attr.aria-valuemax]="token.max_hp" [attr.aria-valuenow]="token.hp">
            <div class="hp-fill" [style.width.%]="(token.hp / token.max_hp) * 100"></div>
          </div>
        </div>
      </div>
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
      width: 50px;
      height: 50px;
      cursor: grab;
      z-index: 10;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .vtt-token:active { cursor: grabbing; }
    .hidden-token { display: none !important; }

    .token-img {
      width: 40px; height: 40px;
      border-radius: 50%;
      object-fit: cover;
      border: 2px solid;
    }
    .enemy-border { border-color: var(--color-red); }
    .player-border { border-color: var(--color-cobalt); }

    .token-fallback {
      width: 40px; height: 40px;
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
    }

    .remove-token-btn {
      position: absolute;
      top: -10px; right: -10px;
      background: var(--color-surface);
      color: var(--color-red);
      border: 1px solid var(--color-red);
      border-radius: 50%;
      width: 28px; height: 28px;
      font-size: 16px;
      line-height: 1;
      display: none;
      cursor: pointer;
    }
    .remove-token-btn:focus-visible {
      outline: 2px solid var(--color-accent);
      outline-offset: 2px;
    }
    .vtt-token:hover .remove-token-btn,
    .vtt-token:focus-within .remove-token-btn {
      display: flex;
      align-items: center;
      justify-content: center;
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

  addCombatantToken(combatantId: string) {
    if (!combatantId) return;
    const combatant = this.combatants.find(c => c.id === combatantId);
    if (!combatant) return;

    const state = this.vttState();
    // Check if token already exists to avoid duplicates
    if (state?.tokens?.some((t: VTTToken) => t.id === combatant.id)) {
      return;
    }

    const token: VTTToken = {
      id: combatant.id,
      name: combatant.name,
      x: 100 + Math.floor(Math.random() * 50),
      y: 100 + Math.floor(Math.random() * 50),
      size: 1,
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
    const url = prompt('Enter map image URL (e.g. from the web):', 'https://i.imgur.com/G4hXqD7.jpg');
    if (url) {
      // Optimistic update
      this.wsService.vttState.update(s => {
        if (!s) return s;
        return { ...s, grid: { ...s.grid, background_image_url: url, cell_size: 50 } };
      });
      this.wsService.sendVttUpdateGrid({ background_image_url: url, cell_size: 50 });
    }
  }
}
