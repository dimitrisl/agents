import { Component, Input, OnInit, effect } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CdkDragEnd, DragDropModule } from '@angular/cdk/drag-drop';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTState, VTTToken } from '../../../core/models/vtt.model';
import { InitiativeCombatant } from '../../../core/models/initiative.model';

@Component({
  selector: 'app-vtt-grid',
  standalone: true,
  imports: [CommonModule, DragDropModule],
  template: `
    <div class="vtt-container" *ngIf="vttState?.is_active" [class.minimized]="isMinimized">
      <!-- Controls -->
      <div class="vtt-controls bg-panel border border-hairline p-2 flex gap-2 justify-between items-center z-10 relative">
        <div class="flex gap-4 items-center">
          <h3 class="text-white font-bold tracking-wider">VTT Grid</h3>
          <ng-container *ngIf="role === 'dm'">
            <div class="flex items-center gap-2">
              <select #combatantSelect style="background: #222; color: #fff; border: 1px solid #555; padding: 4px 8px; border-radius: 4px; font-size: 12px;">
                <option value="">-- Select Combatant --</option>
                <option *ngFor="let c of combatants" [value]="c.id">{{ c.name }}</option>
              </select>
              <button (click)="addCombatantToken(combatantSelect.value)" style="background: #2563eb; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; border: none; cursor: pointer;">Add Token</button>
            </div>
            <button (click)="changeBackground()" style="background: #4b5563; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; border: none; cursor: pointer;">Set Map</button>
          </ng-container>
        </div>
        <div class="flex gap-2">
          <button (click)="toggleMinimize()" style="background: #333; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; border: none; cursor: pointer;">
            {{ isMinimized ? 'Expand' : 'Minimize' }}
          </button>
          <button *ngIf="role === 'dm'" (click)="closeGrid()" style="background: #dc2626; color: #fff; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; border: none; cursor: pointer;">Close Grid</button>
        </div>
      </div>

      <!-- The Grid Canvas -->
      <div class="vtt-canvas" *ngIf="!isMinimized" [style.backgroundImage]="vttState?.grid?.background_image_url ? 'url(' + vttState!.grid!.background_image_url + ')' : 'none'">
        <div class="grid-overlay"
             [style.backgroundSize]="(vttState?.grid?.cell_size || 50) + 'px ' + (vttState?.grid?.cell_size || 50) + 'px'">
        </div>

        <!-- Tokens -->
        <div *ngFor="let token of vttState?.tokens"
             class="vtt-token"
             [class.hidden-token]="token.is_hidden && role !== 'dm'"
             [style.opacity]="token.is_hidden ? 0.5 : 1"
             cdkDrag
             [cdkDragFreeDragPosition]="{x: token.x, y: token.y}"
             (cdkDragEnded)="onDragEnded($event, token)"
             [cdkDragDisabled]="!canMoveToken(token)">

          <img *ngIf="token.image_url" [src]="token.image_url" class="token-img" [class.enemy-border]="token.is_enemy" [class.player-border]="!token.is_enemy">
          <div *ngIf="!token.image_url" class="token-fallback" [class.bg-danger]="token.is_enemy" [class.bg-accent]="!token.is_enemy">
            {{ token.name.charAt(0) }}
          </div>

          <div class="token-label">{{ token.name }}</div>

          <button *ngIf="role === 'dm'" (click)="removeToken(token.id)" class="remove-token-btn" title="Remove Token">×</button>

          <div class="token-hp-bar" *ngIf="token.max_hp && token.hp !== undefined && (role === 'dm' || !token.is_enemy)">
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
      background: #111;
      border: 1px solid var(--color-hairline);
      border-radius: 8px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      margin-top: 24px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      transition: height 0.3s ease;
    }
    .vtt-container.minimized {
      height: 48px;
    }
    .vtt-controls {
      background: #1a1a1a;
      border-bottom: 1px solid #333;
      padding: 12px 20px;
      height: 48px;
      box-sizing: border-box;
    }
    .vtt-canvas {
      flex: 1;
      position: relative;
      overflow: auto;
      background-color: #111;
      background-repeat: no-repeat;
      background-position: top left;
      background-attachment: local;
      box-shadow: inset 0 0 50px rgba(0,0,0,0.8);
    }
    .grid-overlay {
      position: absolute;
      top: 0; left: 0; right: 0; bottom: 0;
      pointer-events: none;
      background-image: linear-gradient(to right, rgba(255,255,255,0.1) 1px, transparent 1px),
                        linear-gradient(to bottom, rgba(255,255,255,0.1) 1px, transparent 1px);
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
    .enemy-border { border-color: #ef4444; }
    .player-border { border-color: #3b82f6; }

    .token-fallback {
      width: 40px; height: 40px;
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: white; font-weight: bold; border: 2px solid rgba(255,255,255,0.5);
    }

    .token-label {
      position: absolute;
      bottom: -15px;
      background: rgba(0,0,0,0.7);
      color: white;
      font-size: 10px;
      padding: 1px 4px;
      border-radius: 4px;
      white-space: nowrap;
    }

    .remove-token-btn {
      position: absolute;
      top: -5px; right: -5px;
      background: #ef4444;
      color: white;
      border: none;
      border-radius: 50%;
      width: 16px; height: 16px;
      font-size: 12px;
      line-height: 12px;
      display: none;
      cursor: pointer;
    }
    .vtt-token:hover .remove-token-btn {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .token-hp-bar {
      position: absolute;
      top: -5px;
      width: 40px;
      height: 4px;
      background: #333;
      border-radius: 2px;
      overflow: hidden;
    }
    .hp-fill {
      height: 100%;
      background: #10b981;
    }
  `]
})
export class VttGridComponent implements OnInit {
  @Input() role: 'dm' | 'player' = 'player';
  @Input() characterName?: string;
  @Input() combatants: InitiativeCombatant[] = [];

  vttState: VTTState | null = null;
  isMinimized: boolean = false;

  constructor(private wsService: WebSocketService) {
    effect(() => {
      this.vttState = this.wsService.vttState();
    });
  }

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
    // Snap to grid (cell_size)
    const cellSize = this.vttState?.grid?.cell_size || 50;
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

    // Check if token already exists to avoid duplicates
    if (this.vttState?.tokens?.some(t => t.id === combatant.id)) {
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
    this.wsService.sendVttAddToken(token);
  }

  removeToken(tokenId: string) {
    this.wsService.sendVttRemoveToken(tokenId);
  }

  changeBackground() {
    const url = prompt('Enter map image URL (e.g. from the web):', 'https://i.imgur.com/G4hXqD7.jpg');
    if (url) {
      this.wsService.sendVttUpdateGrid({ background_image_url: url, cell_size: 50 });
    }
  }
}
