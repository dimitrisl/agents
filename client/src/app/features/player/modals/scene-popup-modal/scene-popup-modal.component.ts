import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  Output,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeModalComponent,
} from '../../../../shared/ui';
import { StoryImageComponent } from '../../../../shared/components/story-image/story-image.component';
import type { ScenePopupPayload } from '../../../../core/models/story-scene.model';

@Component({
  selector: 'app-scene-popup-modal',
  standalone: true,
  imports: [
    CommonModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeModalComponent,
    StoryImageComponent,
  ],
  templateUrl: './scene-popup-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ScenePopupModalComponent {
  @Input() popup: ScenePopupPayload | null = null;
  @Output() dismissed = new EventEmitter<void>();

  get modalTitle(): string {
    return this.popup?.title || 'Visual Handout';
  }

  close(): void {
    this.dismissed.emit();
  }
}
