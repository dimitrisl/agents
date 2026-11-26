import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import {
  MAX_STORY_CARDS,
  StoryCardImageUploadEvent,
  StoryScenesPanelComponent,
} from './story-scenes-panel.component';
import type { StoryScene } from '../../../../core/models/story-scene.model';

describe('StoryScenesPanelComponent', () => {
  let fixture: ComponentFixture<StoryScenesPanelComponent>;
  let component: StoryScenesPanelComponent;

  const sampleScene = (): StoryScene => ({
    scene_id: 'sc-1',
    title: 'Dark Alley',
    dm_notes: 'Ambush',
    cards: [
      {
        card_id: 'card-1',
        title: 'Cloaked Spy',
        image_url: 'https://example.com/spy.png',
        caption: 'A figure steps out of the fog.',
        dm_notes: 'DC 15 Perception',
      },
    ],
  });

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, StoryScenesPanelComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(StoryScenesPanelComponent);
    component = fixture.componentInstance;
  });

  it('targets all vs selected heroes and casts card cleanly in compact mode', () => {
    const emittedCasts: any[] = [];
    component.castCard.subscribe((e) => emittedCasts.push(e));

    fixture.componentRef.setInput('partyMembers', [
      {
        char_id: 'c1',
        name: 'Lyra',
        char_class: 'Rogue',
        level: 4,
        hp_current: 24,
        hp_max: 24,
        ac: 15,
        passive_perception: 14,
        conditions: [],
      },
      {
        char_id: 'c2',
        name: 'Bram',
        char_class: 'Fighter',
        level: 4,
        hp_current: 32,
        hp_max: 32,
        ac: 18,
        passive_perception: 11,
        conditions: [],
      },
    ]);
    fixture.componentRef.setInput('scenes', [sampleScene()]);
    fixture.componentRef.setInput('compact', true);
    fixture.detectChanges();

    const castBtn = fixture.nativeElement.querySelector(
      '[data-testid="cast-card-btn-0"]'
    ) as HTMLButtonElement;
    expect(castBtn.disabled).toBe(false);
    castBtn.click();
    expect(emittedCasts.length).toBe(1);
    expect(emittedCasts[0].targetMode).toBe('all');
    expect(emittedCasts[0].targetCharIds).toEqual([]);

    const selRadio = fixture.nativeElement.querySelector(
      '[data-testid="scene-target-selected"]'
    ) as HTMLButtonElement;
    selRadio.click();
    fixture.detectChanges();
    expect(castBtn.disabled).toBe(true);

    const lyraPill = fixture.nativeElement.querySelector(
      '[data-testid="scene-target-char-c1"]'
    ) as HTMLButtonElement;
    lyraPill.click();
    fixture.detectChanges();
    expect(castBtn.disabled).toBe(false);

    castBtn.click();
    expect(emittedCasts.length).toBe(2);
    expect(emittedCasts[1].targetMode).toBe('selected');
    expect(emittedCasts[1].targetCharIds).toEqual(['c1']);
  });

  it('populates card editor from World Entity picker and keeps dialog open on failed save until saveSuccessSeq bumps', () => {
    const savedScenes: StoryScene[] = [];
    component.saveScene.subscribe((s) => savedScenes.push(s));

    fixture.componentRef.setInput('entities', [
      {
        id: 'ent-1',
        campaign_name: 'Vault',
        name: 'Lord Veylan',
        type: 'villain',
        content: 'Crimson cloak',
        tags: [],
        image_url: 'https://example.com/veylan.png',
      },
    ]);
    fixture.componentRef.setInput('scenes', [sampleScene()]);
    fixture.componentRef.setInput('compact', false);
    fixture.detectChanges();

    component.openNewCard();
    component.onEntitySelect('ent-1');
    expect(component.cardEditor?.draft.image_url).toBe('https://example.com/veylan.png');
    expect(component.cardEditor?.draft.title).toBe('Lord Veylan');
    expect(component.cardEditor?.draft.entity_id).toBe('ent-1');

    // Emit save -> simulate parent error (saving true -> false without saveSuccessSeq bump)
    component.saveCardEditor();
    expect(savedScenes.length).toBe(1);
    expect(savedScenes[0].cards.length).toBe(2);

    fixture.componentRef.setInput('saving', true);
    fixture.detectChanges();
    fixture.componentRef.setInput('saving', false);
    fixture.detectChanges();
    // Dialog and draft must remain open after a failed save!
    expect(component.cardEditor).not.toBeNull();
    expect(component.cardEditor?.draft.title).toBe('Lord Veylan');

    // Retry save -> simulate parent success (saveSuccessSeq increments)
    component.saveCardEditor();
    fixture.componentRef.setInput('saving', true);
    fixture.detectChanges();
    fixture.componentRef.setInput('saving', false);
    fixture.componentRef.setInput('saveSuccessSeq', 1);
    fixture.detectChanges();
    expect(component.cardEditor).toBeNull();
  });

  it('matches uploadedAssetResult strictly by requestId and ignores stale upload replies', () => {
    const uploads: StoryCardImageUploadEvent[] = [];
    component.uploadCardImage.subscribe((u) => uploads.push(u));

    fixture.componentRef.setInput('scenes', [sampleScene()]);
    fixture.componentRef.setInput('compact', false);
    fixture.detectChanges();

    component.openEditCard(0);
    const file = new File(['png'], 'handout.png', { type: 'image/png' });
    component.onFilePicked({ target: { files: [file], value: 'handout.png' } } as unknown as Event);
    expect(uploads.length).toBe(1);
    const reqId = uploads[0].requestId;

    // Stale upload from another session is ignored
    fixture.componentRef.setInput('uploadedAssetResult', {
      requestId: 'stale-other-req',
      url: '/api/v1/campaigns/Vault/assets/wrong.png',
    });
    fixture.detectChanges();
    expect(component.cardEditor?.draft.image_url).toBe('https://example.com/spy.png');

    // Matching requestId updates the editor draft cleanly
    fixture.componentRef.setInput('uploadedAssetResult', {
      requestId: reqId,
      url: '/api/v1/campaigns/Vault/assets/right.png',
    });
    fixture.detectChanges();
    expect(component.cardEditor?.draft.image_url).toBe('/api/v1/campaigns/Vault/assets/right.png');
    expect(component.cardEditor?.requestId).toBeNull();
  });

  it('disables adding cards when scene reaches MAX_STORY_CARDS', () => {
    const fullScene: StoryScene = {
      scene_id: 'sc-full',
      title: 'Full Scene',
      dm_notes: '',
      cards: Array.from({ length: MAX_STORY_CARDS }, (_, i) => ({
        card_id: `card-${i}`,
        title: `Card ${i}`,
        image_url: `https://example.com/${i}.png`,
        caption: '',
        dm_notes: '',
      })),
    };
    fixture.componentRef.setInput('scenes', [fullScene]);
    fixture.componentRef.setInput('compact', false);
    fixture.detectChanges();

    expect(component.canAddCard).toBe(false);
    component.openNewCard();
    expect(component.cardEditor).toBeNull();
  });

  it('closes open card/scene editors when selectedSceneId changes underneath', () => {
    fixture.componentRef.setInput('scenes', [
      sampleScene(),
      { scene_id: 'sc-2', title: 'Other Scene', dm_notes: '', cards: [] },
    ]);
    fixture.componentRef.setInput('selectedSceneId', 'sc-1');
    fixture.componentRef.setInput('compact', false);
    fixture.detectChanges();

    component.openEditCard(0);
    expect(component.cardEditor).not.toBeNull();

    fixture.componentRef.setInput('selectedSceneId', 'sc-2');
    fixture.detectChanges();
    expect(component.cardEditor).toBeNull();
    expect(component.sceneEditor).toBeNull();
  });
});
