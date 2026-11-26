import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeModalComponent } from '../../../../shared/ui';
import {
  StoryCardCastEvent,
  StoryDismissEvent,
  StoryScenesPanelComponent,
} from '../../panels/story-scenes-panel/story-scenes-panel.component';
import type { CampaignEntity } from '../../../../core/models/campaign-entity.model';
import type { PartyMember } from '../../../../core/models/party.model';
import type { StoryScene } from '../../../../core/models/story-scene.model';

@Component({
  selector: 'app-scene-caster-modal',
  standalone: true,
  imports: [CommonModule, ForgeModalComponent, StoryScenesPanelComponent],
  templateUrl: './scene-caster-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SceneCasterModalComponent {
  @Input() open = false;
  @Input() scenes: StoryScene[] = [];
  @Input() partyMembers: PartyMember[] = [];
  @Input() entities: CampaignEntity[] = [];
  @Input() selectedSceneId: string | null = null;
  @Input() loading = false;
  @Input() busyCardId: string | null = null;
  @Input() dismissing = false;
  @Input() lastCastCardId: string | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() selectedSceneIdChange = new EventEmitter<string | null>();
  @Output() castCard = new EventEmitter<StoryCardCastEvent>();
  @Output() dismissPopup = new EventEmitter<StoryDismissEvent>();
  @Output() openPrepEditor = new EventEmitter<void>();
}
