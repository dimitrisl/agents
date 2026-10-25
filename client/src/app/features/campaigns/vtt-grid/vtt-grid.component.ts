import {
  AfterViewInit,
  Component,
  ElementRef,
  Input,
  OnInit,
  ViewChild,
  effect,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { CdkDragEnd, DragDropModule } from '@angular/cdk/drag-drop';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VTTScene, VTTSceneHistory, VTTState, VTTToken } from '../../../core/models/vtt.model';
import { InitiativeCombatant } from '../../../core/models/initiative.model';
import { FormsModule } from '@angular/forms';
import {
  ForgeButtonDirective,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../shared/ui';
import { environment } from '../../../../environments/environment';

@Component({
  selector: 'app-vtt-grid',
  standalone: true,
  imports: [
    CommonModule,
    DragDropModule,
    FormsModule,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
  ],
  template: `
    <div class="vtt-container" *ngIf="vttState()?.is_active" [class.minimized]="isMinimized">
      <!-- Controls -->
      <div class="vtt-controls bg-panel border-b border-hairline p-2 flex gap-2 justify-between items-center z-10 relative">
        <div class="flex gap-4 items-center flex-wrap">
          <div class="flex items-center gap-2">
            <h3 class="text-ink font-bold tracking-wider">VTT Grid</h3>
            <span *ngIf="vttState()?.scene_name" class="text-micro font-medium px-2 py-0.5 rounded bg-surface border border-hairline text-accent">
              🎬 {{ vttState()?.scene_name }}
            </span>
          </div>

          <ng-container *ngIf="role === 'dm'">
            <div class="flex items-center gap-2">
              <select #combatantSelect forgeSelect>
                <option value="">-- Select Combatant --</option>
                <option *ngFor="let c of combatants" [value]="c.id">{{ c.name }}</option>
              </select>
              <button forgeButton variant="primary" size="sm" (click)="addCombatantToken(combatantSelect.value)">Add Token</button>
            </div>
            <button forgeButton variant="secondary" size="sm" (click)="changeBackground()">Set Map</button>
            <button forgeButton variant="secondary" size="sm" (click)="openSceneModal()">🗺️ Scenes</button>

            <!-- Fog DM Toolbar (#157) -->
            <div class="flex items-center gap-1.5 border-l border-hairline pl-3">
              <button
                forgeButton
                [variant]="vttState()?.fog?.enabled ? 'primary' : 'secondary'"
                size="sm"
                (click)="toggleFog()"
                [title]="vttState()?.fog?.enabled ? 'Disable Fog of War' : 'Enable Fog of War'"
              >
                🌫️ Fog: {{ vttState()?.fog?.enabled ? 'ON' : 'OFF' }}
              </button>

              <ng-container *ngIf="vttState()?.fog?.enabled">
                <button
                  forgeButton
                  [variant]="fogBrushMode === 'reveal' ? 'primary' : 'ghost'"
                  size="sm"
                  (click)="setFogBrush('reveal')"
                  title="Reveal Fog Brush (drag on canvas to clear fog)"
                >
                  👁️ Reveal
                </button>
                <button
                  forgeButton
                  [variant]="fogBrushMode === 'hide' ? 'primary' : 'ghost'"
                  size="sm"
                  (click)="setFogBrush('hide')"
                  title="Hide Fog Brush (drag on canvas to conceal fog)"
                >
                  🔒 Hide
                </button>
                <button
                  forgeButton
                  [variant]="fogBrushMode === 'rect_reveal' ? 'primary' : 'ghost'"
                  size="sm"
                  (click)="setFogBrush('rect_reveal')"
                  title="Box Reveal Fog (drag rectangle to clear fog)"
                >
                  🔲 Box Reveal
                </button>
                <button
                  forgeButton
                  [variant]="fogBrushMode === 'rect_hide' ? 'primary' : 'ghost'"
                  size="sm"
                  (click)="setFogBrush('rect_hide')"
                  title="Box Hide Fog (drag rectangle to conceal fog)"
                >
                  ⬛ Box Hide
                </button>
                <button
                  *ngIf="fogBrushMode === 'reveal' || fogBrushMode === 'hide'"
                  forgeButton
                  variant="ghost"
                  size="sm"
                  (click)="toggleBrushSize()"
                  title="Toggle Brush Size (1x1 or 3x3)"
                >
                  {{ fogBrushSize }}x{{ fogBrushSize }}
                </button>
                <button
                  forgeButton
                  variant="ghost"
                  size="sm"
                  (click)="revealAllFog()"
                  title="Reveal entire map to players"
                >
                  Reveal All
                </button>
                <button
                  forgeButton
                  variant="ghost"
                  size="sm"
                  (click)="hideAllFog()"
                  title="Conceal entire map from players"
                >
                  Hide All
                </button>
              </ng-container>
            </div>
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
      <div class="vtt-canvas" *ngIf="!isMinimized" [style.backgroundImage]="getBackgroundImageStyle()">
        <div class="grid-overlay"
             [style.backgroundSize]="(vttState()?.grid?.cell_size || 50) + 'px ' + (vttState()?.grid?.cell_size || 50) + 'px'">
        </div>

        <!-- Fog of War HTML5 Canvas Overlay (#157) -->
        <canvas
          #fogCanvas
          class="fog-canvas"
          [class.paint-mode]="role === 'dm' && !!fogBrushMode"
          [width]="getCanvasWidth()"
          [height]="getCanvasHeight()"
          [style.width.px]="getCanvasWidth()"
          [style.height.px]="getCanvasHeight()"
          (mousedown)="onFogMouseDown($event)"
          (mousemove)="onFogMouseMove($event)"
          (mouseup)="onFogMouseUp()"
          (mouseleave)="onFogMouseUp()"
        ></canvas>

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

      <!-- Scene Manager Modal (#156) -->
      <forge-modal
        [open]="showSceneModal"
        (openChange)="showSceneModal = $event"
        title="🗺️ Campaign Scenes & Maps"
        maxWidth="680px">
        <div class="flex flex-col gap-4 p-2">
          <!-- Error banner -->
          <div *ngIf="sceneError" class="rounded-lg border border-red-500/40 bg-red-950/20 p-3 text-body-sm text-red-300">
            ⚠️ {{ sceneError }}
          </div>

          <!-- Tab Selector -->
          <div class="flex gap-2 border-b border-hairline pb-2">
            <button
              forgeButton
              [variant]="sceneModalTab === 'scenes' ? 'primary' : 'ghost'"
              size="sm"
              type="button"
              (click)="setSceneModalTab('scenes')"
            >
              🗺️ Scenes ({{ scenes.length }})
            </button>
            <button
              forgeButton
              [variant]="sceneModalTab === 'history' ? 'primary' : 'ghost'"
              size="sm"
              type="button"
              (click)="setSceneModalTab('history')"
            >
              📜 Scene History
            </button>
          </div>

          <!-- Scenes Tab Content -->
          <ng-container *ngIf="sceneModalTab === 'scenes'">
            <!-- Loading state -->
            <div *ngIf="loadingScenes" class="flex justify-center py-6">
              <div class="w-8 h-8 border-4 border-gold border-t-transparent rounded-full animate-spin"></div>
            </div>

            <!-- Scene List -->
            <div *ngIf="!loadingScenes" class="flex flex-col gap-2 max-h-[280px] overflow-y-auto">
              <div
                *ngFor="let scene of scenes"
                class="flex flex-col p-3 rounded-lg border border-hairline bg-surface/40 hover:bg-surface/70 transition-colors"
                [class.border-gold]="scene.is_active_scene"
              >
                <div class="flex items-center justify-between">
                  <div class="flex flex-col gap-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="font-semibold text-ink truncate">{{ scene.name }}</span>
                      <span *ngIf="scene.is_active_scene" class="text-micro font-bold px-1.5 py-0.5 rounded bg-gold/20 text-gold border border-gold/40">
                        ACTIVE
                      </span>
                    </div>
                    <div class="text-micro text-muted">
                      Grid: {{ scene.grid.width }}x{{ scene.grid.height }} ({{ scene.grid.cell_size }}px) · Tokens: {{ scene.tokens.length || 0 }} · Fog: {{ scene.fog.enabled ? 'Enabled' : 'Disabled' }}
                    </div>
                  </div>

                  <div class="flex items-center gap-1.5 shrink-0">
                    <button
                      *ngIf="!scene.is_active_scene"
                      forgeButton
                      variant="primary"
                      size="sm"
                      (click)="activateScene(scene)"
                      title="Activate this scene for players"
                    >
                      Activate
                    </button>
                    <button
                      forgeButton
                      [variant]="expandedSceneNotesId === scene.scene_id ? 'primary' : 'ghost'"
                      size="sm"
                      type="button"
                      (click)="toggleSceneNotes(scene)"
                      title="Edit Scene Name & DM Notes"
                    >
                      📝 Notes
                    </button>
                    <button
                      forgeButton
                      variant="ghost"
                      size="sm"
                      (click)="duplicateScene(scene)"
                      title="Duplicate scene"
                    >
                      📑 Clone
                    </button>
                    <button
                      *ngIf="!scene.is_active_scene"
                      forgeButton
                      variant="danger"
                      size="sm"
                      (click)="deleteScene(scene)"
                      title="Delete scene"
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                <!-- Inline DM Notes Editor -->
                <div *ngIf="expandedSceneNotesId === scene.scene_id" class="mt-3 pt-3 border-t border-hairline flex flex-col gap-2">
                  <div>
                    <label class="block text-micro font-semibold text-muted mb-1">Scene Name</label>
                    <input
                      forgeInput
                      type="text"
                      [(ngModel)]="scene.name"
                      class="w-full text-body-sm"
                    />
                  </div>
                  <div>
                    <label class="block text-micro font-semibold text-muted mb-1">DM Notes (Secret)</label>
                    <textarea
                      forgeInput
                      rows="3"
                      [(ngModel)]="scene.dm_notes"
                      placeholder="DM notes, secrets, monster tactics, traps..."
                      class="w-full text-body-sm font-sans"
                    ></textarea>
                  </div>
                  <div class="flex justify-end gap-2 mt-1">
                    <button
                      forgeButton
                      variant="secondary"
                      size="sm"
                      type="button"
                      (click)="expandedSceneNotesId = null"
                    >
                      Cancel
                    </button>
                    <button
                      forgeButton
                      variant="primary"
                      size="sm"
                      type="button"
                      (click)="saveSceneNotes(scene)"
                    >
                      💾 Save Notes
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Create New Scene Form -->
            <div class="border-t border-hairline pt-3 mt-1 flex flex-col gap-3">
              <h4 class="font-semibold text-body-sm text-ink">Create New Scene</h4>
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label class="block text-label text-muted font-semibold mb-1">Scene Name</label>
                  <input
                    forgeInput
                    type="text"
                    placeholder="e.g. Dungeon Level 2"
                    [(ngModel)]="newSceneName"
                    class="w-full text-body"
                  />
                </div>
                <div>
                  <label class="block text-label text-muted font-semibold mb-1">Map Image URL (Optional)</label>
                  <input
                    forgeInput
                    type="text"
                    placeholder="https://..."
                    [(ngModel)]="newSceneMapUrl"
                    class="w-full text-body"
                  />
                </div>
              </div>
              <div class="grid grid-cols-3 gap-3">
                <div>
                  <label class="block text-label text-muted font-semibold mb-1">Width (Cells)</label>
                  <input
                    forgeInput
                    type="number"
                    min="5"
                    max="50"
                    [(ngModel)]="newSceneWidth"
                    class="w-full text-body"
                  />
                </div>
                <div>
                  <label class="block text-label text-muted font-semibold mb-1">Height (Cells)</label>
                  <input
                    forgeInput
                    type="number"
                    min="5"
                    max="50"
                    [(ngModel)]="newSceneHeight"
                    class="w-full text-body"
                  />
                </div>
                <div>
                  <label class="block text-label text-muted font-semibold mb-1">Cell Size (px)</label>
                  <input
                    forgeInput
                    type="number"
                    min="20"
                    max="200"
                    [(ngModel)]="newSceneCellSize"
                    class="w-full text-body"
                  />
                </div>
              </div>
              <div class="flex justify-end gap-2 mt-1">
                <button
                  forgeButton
                  variant="primary"
                  size="sm"
                  type="button"
                  [disabled]="!newSceneName.trim()"
                  (click)="createScene()"
                >
                  + Create Scene
                </button>
              </div>
            </div>
          </ng-container>

          <!-- Scene History Tab Content -->
          <ng-container *ngIf="sceneModalTab === 'history'">
            <div class="flex flex-col gap-2 max-h-[350px] overflow-y-auto">
              <div *ngIf="loadingHistory" class="flex justify-center py-6">
                <div class="w-8 h-8 border-4 border-gold border-t-transparent rounded-full animate-spin"></div>
              </div>
              <div *ngIf="!loadingHistory && sceneHistory.length === 0" class="text-micro text-muted p-4 text-center">
                No scene activation history recorded yet.
              </div>
              <div
                *ngFor="let h of sceneHistory"
                class="flex items-center justify-between p-2.5 rounded-lg border border-hairline bg-surface/30 text-body-sm"
              >
                <div class="flex flex-col gap-0.5">
                  <span class="font-semibold text-ink">🎬 {{ h.scene_name }}</span>
                  <span class="text-micro text-muted">Scene ID: {{ h.scene_id }}</span>
                </div>
                <div class="text-right text-micro text-muted">
                  <div>{{ h.activated_at | date:'medium' }}</div>
                  <div class="text-[10px]">by user: {{ h.activated_by_user_id }}</div>
                </div>
              </div>
            </div>
          </ng-container>

          <div class="flex justify-end border-t border-hairline pt-3 mt-2">
            <button forgeButton variant="secondary" size="sm" type="button" (click)="showSceneModal = false">
              Close
            </button>
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
    .fog-canvas {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 5;
      pointer-events: none;
    }
    .fog-canvas.paint-mode {
      pointer-events: auto;
      cursor: crosshair;
      z-index: 25;
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
      min-width: 28px;
      min-height: 28px;
      height: 28px;
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
      min-width: 28px;
      min-height: 28px;
      width: 28px;
      height: 28px;
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
export class VttGridComponent implements OnInit, AfterViewInit {
  @Input() role: 'dm' | 'player' = 'player';
  @Input() characterName?: string;
  @Input() combatants: InitiativeCombatant[] = [];
  @Input() campaignName?: string;

  @ViewChild('fogCanvas') fogCanvasRef?: ElementRef<HTMLCanvasElement>;

  wsService = inject(WebSocketService);
  http = inject(HttpClient);
  readonly vttState = this.wsService.vttState;

  isMinimized = false;
  showMapModal = false;
  mapUrlInput = '';
  gridSizeInput = 50;

  // Scene management state (#156)
  showSceneModal = false;
  sceneModalTab: 'scenes' | 'history' = 'scenes';
  scenes: VTTScene[] = [];
  sceneHistory: VTTSceneHistory[] = [];
  loadingScenes = false;
  loadingHistory = false;
  sceneError: string | null = null;
  expandedSceneNotesId: string | null = null;
  newSceneName = '';
  newSceneMapUrl = '';
  newSceneCellSize = 50;
  newSceneWidth = 30;
  newSceneHeight = 30;

  // Fog of war state (#157)
  fogBrushMode: 'reveal' | 'hide' | 'rect_reveal' | 'rect_hide' | null = null;
  fogBrushSize = 1; // 1 or 3
  private isPaintingFog = false;
  private paintedFogCells = new Set<string>();
  rectStartCol: number | null = null;
  rectStartRow: number | null = null;
  rectCurrentCol: number | null = null;
  rectCurrentRow: number | null = null;

  // Cached bounding rect on mousedown to avoid layout thrashing during mousemove
  private cachedCanvasRect: DOMRect | null = null;

  // Guard effect cache to prevent redraws on token moves/HP changes
  private lastFogEnabled?: boolean;
  private lastFogRevealed?: number[];
  private lastFogRevealedSet?: Set<number>;
  private lastGridWidth?: number;
  private lastGridHeight?: number;
  private lastGridCellSize?: number;

  private hasFogRevealedChanged(current?: number[]): boolean {
    if (!current && !this.lastFogRevealed) return false;
    if (!current || !this.lastFogRevealed) return true;
    if (current === this.lastFogRevealed) return false;
    if (current.length !== this.lastFogRevealed.length) return true;

    // Fast check: element-by-element equality in order
    const last = this.lastFogRevealed;
    const len = current.length;
    let match = true;
    for (let i = 0; i < len; i++) {
      if (current[i] !== last[i]) {
        match = false;
        break;
      }
    }
    if (match) return false;

    // Fallback: check set membership in case array order changed
    const lastSet = this.lastFogRevealedSet || new Set(last);
    for (let i = 0; i < len; i++) {
      if (!lastSet.has(current[i])) {
        return true;
      }
    }
    return false;
  }

  constructor() {
    effect(() => {
      // Guard component effect: Only trigger renderFogCanvas when fog or grid dimensions change
      const state = this.vttState();
      const fogEnabled = state?.fog?.enabled;
      const fogRevealed = state?.fog?.revealed;
      const gridW = state?.grid?.width;
      const gridH = state?.grid?.height;
      const cellSize = state?.grid?.cell_size;

      const revealedChanged = this.hasFogRevealedChanged(fogRevealed);

      if (
        fogEnabled !== this.lastFogEnabled ||
        revealedChanged ||
        gridW !== this.lastGridWidth ||
        gridH !== this.lastGridHeight ||
        cellSize !== this.lastGridCellSize
      ) {
        this.lastFogEnabled = fogEnabled;
        this.lastFogRevealed = fogRevealed ? [...fogRevealed] : undefined;
        this.lastFogRevealedSet = fogRevealed ? new Set(fogRevealed) : undefined;
        this.lastGridWidth = gridW;
        this.lastGridHeight = gridH;
        this.lastGridCellSize = cellSize;
        requestAnimationFrame(() => this.renderFogCanvas());
      }
    });
  }

  ngOnInit(): void {}

  ngAfterViewInit(): void {
    this.renderFogCanvas();
  }

  getCanvasWidth(): number {
    const grid = this.vttState()?.grid;
    return (grid?.width || 30) * (grid?.cell_size || 50);
  }

  getCanvasHeight(): number {
    const grid = this.vttState()?.grid;
    return (grid?.height || 30) * (grid?.cell_size || 50);
  }

  getBackgroundImageStyle(): string {
    const url = this.vttState()?.grid?.background_image_url;
    if (!url) return 'none';
    const safeUrl = url.replace(/["\\\n\r]/g, '');
    return `url("${safeUrl}")`;
  }

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
    this.wsService.vttState.update((s) => {
      if (!s) return s;
      return {
        ...s,
        tokens: s.tokens.map((t) =>
          t.id === token.id ? { ...t, x: snappedX, y: snappedY } : t
        ),
      };
    });

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
    const existingTokens = state?.tokens || [];
    const alreadyExists = existingTokens.some((t: VTTToken) => t.id === combatant.id);
    // Check if player token already exists to avoid duplicate hero tokens
    if (alreadyExists && combatant.is_player) {
      return;
    }

    let tokenName = combatant.name;
    const sameNameTokens = existingTokens.filter(t =>
      t.name.toLowerCase() === combatant.name.toLowerCase() ||
      new RegExp(`^${combatant.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*#\\d+$`, 'i').test(t.name)
    );
    if (sameNameTokens.length > 0 && !/(\s+\d+|\s*#\d+)$/.test(combatant.name)) {
      tokenName = `${combatant.name} #${sameNameTokens.length + 1}`;
    }

    const tokenId = alreadyExists
      ? `${combatant.id}_${sameNameTokens.length + 1}`
      : combatant.id;

    const token: VTTToken = {
      id: tokenId,
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

  // --- Fog of War (#157) ---

  toggleFog(): void {
    if (this.role !== 'dm') return;
    const current = !!this.vttState()?.fog?.enabled;
    this.wsService.sendVttFogToggle(!current);
  }

  setFogBrush(mode: 'reveal' | 'hide' | 'rect_reveal' | 'rect_hide' | null): void {
    this.fogBrushMode = this.fogBrushMode === mode ? null : mode;
    this.rectStartCol = null;
    this.rectStartRow = null;
    this.rectCurrentCol = null;
    this.rectCurrentRow = null;
  }

  toggleBrushSize(): void {
    this.fogBrushSize = this.fogBrushSize === 1 ? 3 : 1;
  }

  revealAllFog(): void {
    if (this.role !== 'dm') return;
    this.wsService.sendVttFogRevealAll();
  }

  hideAllFog(): void {
    if (this.role !== 'dm') return;
    this.wsService.sendVttFogHideAll();
  }

  renderFogCanvas(): void {
    const canvas = this.fogCanvasRef?.nativeElement;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const state = this.vttState();
    const grid = state?.grid;
    const fog = state?.fog;
    const width = grid?.width || 30;
    const height = grid?.height || 30;
    const cellSize = grid?.cell_size || 50;
    const totalW = width * cellSize;
    const totalH = height * cellSize;

    ctx.clearRect(0, 0, totalW, totalH);

    if (!fog?.enabled) {
      return;
    }

    // Punch-Out rendering: Fill entire canvas once with fog color
    ctx.fillStyle = this.role === 'dm' ? 'rgba(15, 23, 42, 0.70)' : '#0a0d14';
    ctx.fillRect(0, 0, totalW, totalH);

    // Punch out transparent holes for revealed cells (no redundant strokeRect calls)
    const revealed = fog.revealed || [];
    for (let i = 0; i < revealed.length; i++) {
      const idx = revealed[i];
      if (idx >= 0 && idx < width * height) {
        const rx = (idx % width) * cellSize;
        const ry = Math.floor(idx / width) * cellSize;
        ctx.clearRect(rx, ry, cellSize, cellSize);
      }
    }

    // Live brush drag preview: render transient painted cells while dragging
    if (this.isPaintingFog && this.paintedFogCells.size > 0) {
      if (this.fogBrushMode === 'reveal') {
        this.paintedFogCells.forEach((coord) => {
          const [cx, cy] = coord.split(',').map(Number);
          ctx.clearRect(cx * cellSize, cy * cellSize, cellSize, cellSize);
          ctx.fillStyle = 'rgba(56, 189, 248, 0.25)';
          ctx.fillRect(cx * cellSize, cy * cellSize, cellSize, cellSize);
        });
      } else if (this.fogBrushMode === 'hide') {
        ctx.fillStyle = this.role === 'dm' ? 'rgba(15, 23, 42, 0.70)' : '#0a0d14';
        this.paintedFogCells.forEach((coord) => {
          const [cx, cy] = coord.split(',').map(Number);
          ctx.fillRect(cx * cellSize, cy * cellSize, cellSize, cellSize);
        });
        ctx.fillStyle = 'rgba(244, 63, 94, 0.25)';
        this.paintedFogCells.forEach((coord) => {
          const [cx, cy] = coord.split(',').map(Number);
          ctx.fillRect(cx * cellSize, cy * cellSize, cellSize, cellSize);
        });
      }
    }

    // Render interactive rectangle fog selection preview (#157)
    if (
      this.rectStartCol !== null &&
      this.rectCurrentCol !== null &&
      this.rectStartRow !== null &&
      this.rectCurrentRow !== null
    ) {
      const minCol = Math.min(this.rectStartCol, this.rectCurrentCol);
      const maxCol = Math.max(this.rectStartCol, this.rectCurrentCol);
      const minRow = Math.min(this.rectStartRow, this.rectCurrentRow);
      const maxRow = Math.max(this.rectStartRow, this.rectCurrentRow);
      const px = minCol * cellSize;
      const py = minRow * cellSize;
      const pw = (maxCol - minCol + 1) * cellSize;
      const ph = (maxRow - minRow + 1) * cellSize;

      ctx.save();
      ctx.strokeStyle = this.fogBrushMode === 'rect_reveal' ? '#38bdf8' : '#f43f5e';
      ctx.lineWidth = 2;
      ctx.setLineDash([4, 4]);
      ctx.strokeRect(px, py, pw, ph);
      ctx.fillStyle =
        this.fogBrushMode === 'rect_reveal'
          ? 'rgba(56, 189, 248, 0.25)'
          : 'rgba(244, 63, 94, 0.25)';
      ctx.fillRect(px, py, pw, ph);
      ctx.restore();
    }
  }

  onFogMouseDown(event: MouseEvent): void {
    if (this.role !== 'dm' || !this.fogBrushMode) return;
    event.preventDefault();
    this.isPaintingFog = true;

    // Cache canvas.getBoundingClientRect() on mousedown to avoid layout thrashing during mousemove
    const canvas = this.fogCanvasRef?.nativeElement;
    if (canvas) {
      this.cachedCanvasRect = canvas.getBoundingClientRect();
    }

    if (this.fogBrushMode === 'rect_reveal' || this.fogBrushMode === 'rect_hide') {
      const cell = this.getCellCoordsAtMouse(event);
      if (cell) {
        this.rectStartCol = cell.cx;
        this.rectStartRow = cell.cy;
        this.rectCurrentCol = cell.cx;
        this.rectCurrentRow = cell.cy;
        this.renderFogCanvas();
      }
    } else {
      this.paintedFogCells.clear();
      this.addCellAtMouse(event);
      this.renderFogCanvas();
    }
  }

  onFogMouseMove(event: MouseEvent): void {
    if (!this.isPaintingFog || !this.fogBrushMode) return;
    if (this.fogBrushMode === 'rect_reveal' || this.fogBrushMode === 'rect_hide') {
      const cell = this.getCellCoordsAtMouse(event);
      if (cell && (cell.cx !== this.rectCurrentCol || cell.cy !== this.rectCurrentRow)) {
        this.rectCurrentCol = cell.cx;
        this.rectCurrentRow = cell.cy;
        this.renderFogCanvas();
      }
    } else {
      const prevSize = this.paintedFogCells.size;
      this.addCellAtMouse(event);
      if (this.paintedFogCells.size !== prevSize) {
        // Live brush drag preview
        this.renderFogCanvas();
      }
    }
  }

  onFogMouseUp(): void {
    if (!this.isPaintingFog || !this.fogBrushMode) return;
    this.isPaintingFog = false;
    this.cachedCanvasRect = null;

    const state = this.vttState();
    const gridW = state?.grid?.width || 30;
    const gridH = state?.grid?.height || 30;

    if (
      (this.fogBrushMode === 'rect_reveal' || this.fogBrushMode === 'rect_hide') &&
      this.rectStartCol !== null &&
      this.rectCurrentCol !== null &&
      this.rectStartRow !== null &&
      this.rectCurrentRow !== null
    ) {
      const minCol = Math.min(this.rectStartCol, this.rectCurrentCol);
      const maxCol = Math.max(this.rectStartCol, this.rectCurrentCol);
      const minRow = Math.min(this.rectStartRow, this.rectCurrentRow);
      const maxRow = Math.max(this.rectStartRow, this.rectCurrentRow);
      const rectPayload = {
        x: minCol,
        y: minRow,
        w: maxCol - minCol + 1,
        h: maxRow - minRow + 1,
      };

      const isReveal = this.fogBrushMode === 'rect_reveal';
      const affectedIndices: number[] = [];
      for (let r = minRow; r <= maxRow; r++) {
        for (let c = minCol; c <= maxCol; c++) {
          if (c >= 0 && c < gridW && r >= 0 && r < gridH) {
            affectedIndices.push(r * gridW + c);
          }
        }
      }

      // Optimistic update on mouseup: 0 ms perceived latency
      this.wsService.vttState.update((s) => {
        if (!s) return s;
        const currentRevealed = new Set(s.fog?.revealed || []);
        if (isReveal) {
          affectedIndices.forEach((idx) => currentRevealed.add(idx));
        } else {
          affectedIndices.forEach((idx) => currentRevealed.delete(idx));
        }
        return {
          ...s,
          fog: {
            enabled: s.fog?.enabled ?? true,
            revealed: Array.from(currentRevealed),
          },
        };
      });

      const updatedRevealed = this.vttState()?.fog?.revealed;
      this.lastFogRevealed = updatedRevealed ? [...updatedRevealed] : undefined;
      this.lastFogRevealedSet = updatedRevealed ? new Set(updatedRevealed) : undefined;

      if (isReveal) {
        this.wsService.sendVttFogReveal(undefined, rectPayload);
      } else {
        this.wsService.sendVttFogHide(undefined, rectPayload);
      }

      this.rectStartCol = null;
      this.rectStartRow = null;
      this.rectCurrentCol = null;
      this.rectCurrentRow = null;
      this.renderFogCanvas();
      return;
    }

    if (this.paintedFogCells.size > 0) {
      const cells: number[][] = [];
      const affectedIndices: number[] = [];
      const isReveal = this.fogBrushMode === 'reveal';

      this.paintedFogCells.forEach((coord) => {
        const [x, y] = coord.split(',').map(Number);
        cells.push([x, y]);
        if (x >= 0 && x < gridW && y >= 0 && y < gridH) {
          affectedIndices.push(y * gridW + x);
        }
      });

      // Optimistic update on mouseup: 0 ms perceived latency
      this.wsService.vttState.update((s) => {
        if (!s) return s;
        const currentRevealed = new Set(s.fog?.revealed || []);
        if (isReveal) {
          affectedIndices.forEach((idx) => currentRevealed.add(idx));
        } else {
          affectedIndices.forEach((idx) => currentRevealed.delete(idx));
        }
        return {
          ...s,
          fog: {
            enabled: s.fog?.enabled ?? true,
            revealed: Array.from(currentRevealed),
          },
        };
      });

      const updatedRevealed = this.vttState()?.fog?.revealed;
      this.lastFogRevealed = updatedRevealed ? [...updatedRevealed] : undefined;
      this.lastFogRevealedSet = updatedRevealed ? new Set(updatedRevealed) : undefined;

      if (isReveal) {
        this.wsService.sendVttFogReveal(cells);
      } else if (this.fogBrushMode === 'hide') {
        this.wsService.sendVttFogHide(cells);
      }
      this.paintedFogCells.clear();
      this.renderFogCanvas();
    }
  }

  private getCellCoordsAtMouse(event: MouseEvent): { cx: number; cy: number } | null {
    const canvas = this.fogCanvasRef?.nativeElement;
    if (!canvas) return null;
    const rect = this.cachedCanvasRect || canvas.getBoundingClientRect();
    const cellSize = this.vttState()?.grid?.cell_size || 50;
    const gridW = this.vttState()?.grid?.width || 30;
    const gridH = this.vttState()?.grid?.height || 30;

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const cx = Math.max(0, Math.min(gridW - 1, Math.floor(mouseX / cellSize)));
    const cy = Math.max(0, Math.min(gridH - 1, Math.floor(mouseY / cellSize)));
    return { cx, cy };
  }

  private addCellAtMouse(event: MouseEvent): void {
    const canvas = this.fogCanvasRef?.nativeElement;
    if (!canvas) return;
    const rect = this.cachedCanvasRect || canvas.getBoundingClientRect();
    const cellSize = this.vttState()?.grid?.cell_size || 50;
    const gridW = this.vttState()?.grid?.width || 30;
    const gridH = this.vttState()?.grid?.height || 30;

    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const cx = Math.floor(mouseX / cellSize);
    const cy = Math.floor(mouseY / cellSize);

    const radius = this.fogBrushSize === 3 ? 1 : 0;
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        const targetX = cx + dx;
        const targetY = cy + dy;
        if (targetX >= 0 && targetX < gridW && targetY >= 0 && targetY < gridH) {
          this.paintedFogCells.add(`${targetX},${targetY}`);
        }
      }
    }
  }

  // --- Scene Management (#156) ---

  openSceneModal(): void {
    this.sceneError = null;
    this.sceneModalTab = 'scenes';
    this.expandedSceneNotesId = null;
    this.loadScenes();
    this.showSceneModal = true;
  }

  setSceneModalTab(tab: 'scenes' | 'history'): void {
    this.sceneModalTab = tab;
    this.sceneError = null;
    if (tab === 'history') {
      this.loadSceneHistory();
    } else {
      this.loadScenes();
    }
  }

  toggleSceneNotes(scene: VTTScene): void {
    this.expandedSceneNotesId =
      this.expandedSceneNotesId === scene.scene_id ? null : scene.scene_id;
  }

  loadSceneHistory(): void {
    if (!this.campaignName) return;
    this.loadingHistory = true;
    this.http
      .get<VTTSceneHistory[]>(
        `${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes/history`
      )
      .subscribe({
        next: (history) => {
          this.sceneHistory = history;
          this.loadingHistory = false;
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to load scene history.';
          this.loadingHistory = false;
        },
      });
  }

  saveSceneNotes(scene: VTTScene): void {
    if (!this.campaignName) return;
    const body = {
      name: scene.name,
      dm_notes: scene.dm_notes,
    };
    this.http
      .put<VTTScene>(
        `${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes/${scene.scene_id}`,
        body
      )
      .subscribe({
        next: (updated) => {
          scene.name = updated.name;
          scene.dm_notes = updated.dm_notes;
          this.expandedSceneNotesId = null;
          this.loadScenes();
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to update scene notes.';
        },
      });
  }

  loadScenes(): void {
    if (!this.campaignName) return;
    this.loadingScenes = true;
    this.http.get<VTTScene[]>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes`)
      .subscribe({
        next: (scenes) => {
          this.scenes = scenes;
          this.loadingScenes = false;
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to load scenes.';
          this.loadingScenes = false;
        }
      });
  }

  createScene(): void {
    if (!this.campaignName || !this.newSceneName.trim()) return;
    const body = {
      name: this.newSceneName.trim(),
      grid: {
        background_image_url: this.newSceneMapUrl.trim() || undefined,
        cell_size: Number(this.newSceneCellSize) || 50,
        width: Number(this.newSceneWidth) || 30,
        height: Number(this.newSceneHeight) || 30,
      },
    };
    this.http.post<VTTScene>(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes`, body)
      .subscribe({
        next: () => {
          this.newSceneName = '';
          this.newSceneMapUrl = '';
          this.loadScenes();
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to create scene.';
        }
      });
  }

  activateScene(scene: VTTScene): void {
    if (!this.campaignName || scene.is_active_scene) return;
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes/${scene.scene_id}/activate`, {})
      .subscribe({
        next: () => {
          this.loadScenes();
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to activate scene.';
        }
      });
  }

  duplicateScene(scene: VTTScene): void {
    if (!this.campaignName) return;
    this.http.post(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes/${scene.scene_id}/duplicate`, {})
      .subscribe({
        next: () => {
          this.loadScenes();
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to duplicate scene.';
        }
      });
  }

  deleteScene(scene: VTTScene): void {
    if (!this.campaignName) return;
    if (scene.is_active_scene) {
      this.sceneError = 'Cannot delete active scene. Switch to another scene first.';
      return;
    }
    if (!window.confirm(`Are you sure you want to delete scene "${scene.name}"?`)) return;

    this.http.delete(`${environment.apiBaseUrl}/campaigns/${this.campaignName}/scenes/${scene.scene_id}`)
      .subscribe({
        next: () => {
          this.loadScenes();
        },
        error: (err) => {
          this.sceneError = err.error?.detail || 'Failed to delete scene.';
        }
      });
  }
}
