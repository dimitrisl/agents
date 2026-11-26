import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeEmptyStateComponent,
  ForgeIconComponent,
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeSelectDirective,
  ForgeSpinnerComponent,
  ForgeTextareaDirective,
} from '../../../../shared/ui';
import { StoryImageComponent } from '../../../../shared/components/story-image/story-image.component';
import type { CampaignEntity } from '../../../../core/models/campaign-entity.model';
import type { PartyMember } from '../../../../core/models/party.model';
import type {
  StoryScene,
  StorySceneCard,
  StoryTargetMode,
} from '../../../../core/models/story-scene.model';

export const MAX_STORY_CARDS = 50;

/** Upload request raised from the card editor; `requestId` ties the reply to one editor session. */
export interface StoryCardImageUploadEvent {
  requestId: string;
  file: File;
}

export interface StoryUploadResult {
  requestId: string;
  url: string;
}

export interface StoryCardCastEvent {
  scene: StoryScene;
  card: StorySceneCard;
  /** True when `scene` carries unsaved edits that must be persisted before casting. */
  dirty: boolean;
  targetMode: StoryTargetMode;
  targetCharIds: string[];
}

export interface StoryDismissEvent {
  targetMode: StoryTargetMode;
  targetCharIds: string[];
}

export interface StorySceneReorderEvent {
  sceneId: string;
  direction: -1 | 1;
}

type ImageSource = 'upload' | 'url' | 'vault';

interface CardEditorState {
  /** `null` = a brand-new card appended on save. */
  index: number | null;
  draft: StorySceneCard;
  /** Pending upload for this editor session, if any. */
  requestId: string | null;
}

interface SceneEditorState {
  title: string;
  dm_notes: string;
}

/**
 * Presentational Story Scenes panel (#288).
 *
 * Prep mode shows the scene as a grid of image tiles; every edit happens in a
 * focused dialog that saves straight to the server, so there is no page-level
 * "unsaved" draft to lose on a tab switch. Compact mode (Live DM / caster modal)
 * is read-only: pick a scene, pick who sees it, press Show.
 */
@Component({
  selector: 'app-story-scenes-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeEmptyStateComponent,
    ForgeIconComponent,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeSelectDirective,
    ForgeSpinnerComponent,
    ForgeTextareaDirective,
    StoryImageComponent,
  ],
  templateUrl: './story-scenes-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StoryScenesPanelComponent implements OnChanges {
  @Input() scenes: StoryScene[] = [];
  @Input() partyMembers: PartyMember[] = [];
  @Input() entities: CampaignEntity[] = [];
  @Input() compact = false;
  @Input() loading = false;
  @Input() saving = false;
  @Input() uploadingRequestId: string | null = null;
  @Input() busyCardId: string | null = null;
  @Input() dismissing = false;
  @Input() lastCastCardId: string | null = null;
  @Input() uploadedAssetResult: StoryUploadResult | null = null;
  /** Bumped by the parent after every successful scene save; closes the open dialog. */
  @Input() saveSuccessSeq = 0;
  @Input() selectedSceneId: string | null = null;

  @Output() createScene = new EventEmitter<{ title: string }>();
  @Output() saveScene = new EventEmitter<StoryScene>();
  @Output() deleteScene = new EventEmitter<StoryScene>();
  @Output() reorderScene = new EventEmitter<StorySceneReorderEvent>();
  @Output() uploadCardImage = new EventEmitter<StoryCardImageUploadEvent>();
  @Output() castCard = new EventEmitter<StoryCardCastEvent>();
  @Output() dismissPopup = new EventEmitter<StoryDismissEvent>();
  @Output() openPrepEditor = new EventEmitter<void>();
  @Output() selectedSceneIdChange = new EventEmitter<string | null>();

  readonly maxCards = MAX_STORY_CARDS;

  newSceneTitle = '';
  targetMode: StoryTargetMode = 'all';
  selectedCharIds: string[] = [];

  cardEditor: CardEditorState | null = null;
  sceneEditor: SceneEditorState | null = null;
  imageSource: ImageSource = 'upload';
  private pendingCloseOnSave = false;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['selectedSceneId'] && !changes['selectedSceneId'].firstChange) {
      this.cardEditor = null;
      this.sceneEditor = null;
      this.pendingCloseOnSave = false;
    }
    if (changes['saveSuccessSeq'] && !changes['saveSuccessSeq'].firstChange && this.pendingCloseOnSave) {
      this.pendingCloseOnSave = false;
      this.cardEditor = null;
      this.sceneEditor = null;
    }
    if (changes['saving'] && !this.saving && this.pendingCloseOnSave && !changes['saveSuccessSeq']) {
      // Save finished without a success bump: keep the dialog (and the draft) open.
      this.pendingCloseOnSave = false;
    }
    if (changes['uploadedAssetResult'] && this.uploadedAssetResult && this.cardEditor) {
      const res = this.uploadedAssetResult;
      if (this.cardEditor.requestId && this.cardEditor.requestId === res.requestId) {
        this.cardEditor = {
          ...this.cardEditor,
          requestId: null,
          draft: { ...this.cardEditor.draft, image_url: res.url, entity_id: null },
        };
      }
    }
    if (changes['partyMembers']) {
      const validIds = new Set(this.targetableMembers.map((m) => m.char_id!));
      this.selectedCharIds = this.selectedCharIds.filter((id) => validIds.has(id));
    }
  }

  // --- Derived state ---

  get activeScene(): StoryScene | null {
    if (!this.scenes.length) return null;
    return this.scenes.find((s) => s.scene_id === this.selectedSceneId) ?? this.scenes[0];
  }

  get targetableMembers(): PartyMember[] {
    return (this.partyMembers || []).filter((m) => !!m.char_id);
  }

  get entitiesWithImages(): CampaignEntity[] {
    return (this.entities || []).filter((e) => !!(e.image_url || '').trim());
  }

  get audienceLabel(): string {
    if (this.targetMode === 'all') return 'everyone';
    const names = this.targetableMembers
      .filter((m) => this.selectedCharIds.includes(m.char_id!))
      .map((m) => m.name);
    return names.length ? names.join(', ') : 'nobody yet';
  }

  get editorTitleInvalid(): boolean {
    return !!this.cardEditor && !this.cardEditor.draft.title.trim();
  }

  get editorUploading(): boolean {
    return !!this.cardEditor?.requestId && this.uploadingRequestId === this.cardEditor.requestId;
  }

  get canAddCard(): boolean {
    return !!this.activeScene && this.activeScene.cards.length < this.maxCards;
  }

  // --- Scene list ---

  selectScene(scene: StoryScene): void {
    this.selectedSceneIdChange.emit(scene.scene_id ?? null);
  }

  isSceneActive(scene: StoryScene): boolean {
    return !!scene.scene_id && scene.scene_id === this.activeScene?.scene_id;
  }

  submitNewScene(): void {
    const clean = this.newSceneTitle.trim();
    if (!clean) return;
    this.createScene.emit({ title: clean });
    this.newSceneTitle = '';
  }

  openSceneEditor(): void {
    const scene = this.activeScene;
    if (!scene) return;
    this.sceneEditor = { title: scene.title, dm_notes: scene.dm_notes || '' };
  }

  closeSceneEditor(): void {
    this.sceneEditor = null;
    this.pendingCloseOnSave = false;
  }

  saveSceneEditor(): void {
    const scene = this.activeScene;
    if (!scene || !this.sceneEditor || !this.sceneEditor.title.trim()) return;
    this.pendingCloseOnSave = true;
    this.saveScene.emit({
      ...scene,
      title: this.sceneEditor.title.trim(),
      dm_notes: this.sceneEditor.dm_notes,
      cards: this.normalizedCards(scene.cards),
    });
  }

  // --- Card editor ---

  openNewCard(): void {
    if (!this.canAddCard) return;
    this.imageSource = 'upload';
    this.cardEditor = {
      index: null,
      requestId: null,
      draft: {
        card_id: this.generateId('card'),
        title: '',
        image_url: '',
        caption: '',
        dm_notes: '',
        entity_id: null,
      },
    };
  }

  openEditCard(index: number): void {
    const card = this.activeScene?.cards[index];
    if (!card) return;
    this.imageSource = card.entity_id ? 'vault' : card.image_url && !card.image_url.startsWith('/') ? 'url' : 'upload';
    this.cardEditor = {
      index,
      requestId: null,
      draft: {
        card_id: card.card_id,
        title: card.title || '',
        image_url: card.image_url || '',
        caption: card.caption || '',
        dm_notes: card.dm_notes || '',
        entity_id: card.entity_id ?? null,
      },
    };
  }

  closeCardEditor(): void {
    this.cardEditor = null;
    this.pendingCloseOnSave = false;
  }

  setImageSource(source: ImageSource): void {
    this.imageSource = source;
  }

  saveCardEditor(): void {
    const scene = this.buildSceneWithEditorDraft();
    if (!scene || this.editorTitleInvalid || this.editorUploading || this.saving || this.busyCardId) return;
    this.pendingCloseOnSave = true;
    this.saveScene.emit(scene);
  }

  saveAndShowCardEditor(): void {
    const scene = this.buildSceneWithEditorDraft();
    if (
      !scene ||
      !this.cardEditor ||
      this.editorTitleInvalid ||
      this.editorUploading ||
      this.saving ||
      this.busyCardId
    ) {
      return;
    }
    if (!this.canCastCard(this.cardEditor.draft)) return;
    this.pendingCloseOnSave = true;
    this.castCard.emit({
      scene,
      card: { ...this.cardEditor.draft, title: this.cardEditor.draft.title.trim() },
      dirty: true,
      targetMode: this.targetMode,
      targetCharIds: this.targetMode === 'selected' ? [...this.selectedCharIds] : [],
    });
  }

  removeEditorCard(): void {
    const scene = this.activeScene;
    if (!scene || !this.cardEditor || this.cardEditor.index === null || this.saving || this.busyCardId) return;
    const idx = this.cardEditor.index;
    this.pendingCloseOnSave = true;
    this.saveScene.emit({
      ...scene,
      cards: this.normalizedCards(scene.cards.filter((_, i) => i !== idx)),
    });
  }

  moveCard(index: number, delta: -1 | 1): void {
    const scene = this.activeScene;
    if (!scene) return;
    const target = index + delta;
    if (target < 0 || target >= scene.cards.length) return;
    const copy = [...scene.cards];
    const [item] = copy.splice(index, 1);
    copy.splice(target, 0, item);
    this.saveScene.emit({ ...scene, cards: this.normalizedCards(copy) });
  }

  onEntitySelect(entityId: string | null): void {
    if (!this.cardEditor) return;
    const match = this.entitiesWithImages.find((e) => (e.id || e.name) === entityId);
    const draft = this.cardEditor.draft;
    this.cardEditor = {
      ...this.cardEditor,
      draft: match
        ? {
            ...draft,
            entity_id: match.id || match.name,
            image_url: match.image_url || draft.image_url,
            title: draft.title.trim() ? draft.title : match.name,
          }
        : { ...draft, entity_id: null },
    };
  }

  onFilePicked(event: Event): void {
    const input = event.target as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (file) this.startUpload(file);
    if (input) input.value = '';
  }

  onDropImage(event: DragEvent): void {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file && file.type.startsWith('image/')) this.startUpload(file);
  }

  onPasteImage(event: ClipboardEvent): void {
    const items = event.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile();
        if (file) {
          event.preventDefault();
          this.startUpload(file);
          return;
        }
      }
    }
  }

  private startUpload(file: File): void {
    if (!this.cardEditor) return;
    const requestId = this.generateId('upload');
    this.cardEditor = { ...this.cardEditor, requestId };
    this.uploadCardImage.emit({ requestId, file });
  }

  private buildSceneWithEditorDraft(): StoryScene | null {
    const scene = this.activeScene;
    if (!scene || !this.cardEditor) return null;
    const draft = { ...this.cardEditor.draft, title: this.cardEditor.draft.title.trim() };
    const cards =
      this.cardEditor.index === null
        ? [...scene.cards, draft]
        : scene.cards.map((c, i) => (i === this.cardEditor!.index ? draft : c));
    return { ...scene, cards: this.normalizedCards(cards) };
  }

  private normalizedCards(cards: StorySceneCard[]): StorySceneCard[] {
    return cards.map((c, idx) => ({ ...c, order: idx }));
  }

  // --- Audience & casting ---

  setTargetMode(mode: StoryTargetMode): void {
    this.targetMode = mode;
  }

  toggleTargetChar(charId: string): void {
    this.selectedCharIds = this.selectedCharIds.includes(charId)
      ? this.selectedCharIds.filter((id) => id !== charId)
      : [...this.selectedCharIds, charId];
  }

  isCharSelected(charId: string | undefined): boolean {
    return !!charId && this.selectedCharIds.includes(charId);
  }

  canCastCard(card: StorySceneCard): boolean {
    if (!(card.image_url || '').trim()) return false;
    if (this.targetMode === 'selected' && this.selectedCharIds.length === 0) return false;
    return true;
  }

  onCastCard(card: StorySceneCard): void {
    const scene = this.activeScene;
    if (!scene || !this.canCastCard(card)) return;
    this.castCard.emit({
      scene,
      card: { ...card },
      dirty: false,
      targetMode: this.targetMode,
      targetCharIds: this.targetMode === 'selected' ? [...this.selectedCharIds] : [],
    });
  }

  onDismissPopup(): void {
    this.dismissPopup.emit({
      targetMode: this.targetMode,
      targetCharIds: this.targetMode === 'selected' ? [...this.selectedCharIds] : [],
    });
  }

  private generateId(prefix: string): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  }
}
