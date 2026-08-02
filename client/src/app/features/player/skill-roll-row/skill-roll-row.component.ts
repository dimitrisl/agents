import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { NgClass } from '@angular/common';
import { ForgeBadgeComponent, ForgeButtonDirective } from '../../../shared/ui';
import type { SkillDefinition } from '../player.component';

@Component({
  selector: 'app-skill-roll-row',
  standalone: true,
  imports: [NgClass, ForgeBadgeComponent, ForgeButtonDirective],
  templateUrl: './skill-roll-row.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkillRollRowComponent {
  @Input({ required: true }) skill!: SkillDefinition;
  @Input() proficient = false;
  @Input() modifier = '+0';

  @Output() roll = new EventEmitter<SkillDefinition>();
}
