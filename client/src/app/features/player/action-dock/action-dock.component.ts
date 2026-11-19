import { ChangeDetectionStrategy, Component, EventEmitter, Output, Input } from '@angular/core';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-action-dock',
  standalone: true,
  imports: [ForgeButtonDirective],
  templateUrl: './action-dock.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ActionDockComponent {
  @Input() canLevelUp = true;
  @Input() isGeneratingStrategy = false;
  /** The level-up analysis is an AI call; spins the button until it answers. */
  @Input() isLevelUpLoading = false;
  @Input() isInCampaign = false;
  @Input() shortRestUnlocked = false;
  @Input() longRestUnlocked = false;
  @Input() levelUpUnlocked = false;
  @Input() isDeceasedByExhaustion = false;

  get canShortRest(): boolean {
    if (this.isDeceasedByExhaustion) return false;
    return !this.isInCampaign || this.shortRestUnlocked;
  }

  get canLongRest(): boolean {
    if (this.isDeceasedByExhaustion) return false;
    return !this.isInCampaign || this.longRestUnlocked;
  }

  get canTriggerLevelUp(): boolean {
    if (!this.canLevelUp || this.isDeceasedByExhaustion) return false;
    return !this.isInCampaign || this.levelUpUnlocked;
  }

  @Output() shortRest = new EventEmitter<void>();
  @Output() longRest = new EventEmitter<void>();
  @Output() levelUp = new EventEmitter<void>();
  @Output() audit = new EventEmitter<void>();
  @Output() strategy = new EventEmitter<void>();
  @Output() exportPdf = new EventEmitter<void>();
  @Output() importCharacter = new EventEmitter<void>();
  @Output() dodge = new EventEmitter<void>();
  @Output() dash = new EventEmitter<void>();
  @Output() disengage = new EventEmitter<void>();
  @Output() help = new EventEmitter<void>();
}
