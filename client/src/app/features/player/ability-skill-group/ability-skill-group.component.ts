import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import type { SkillDefinition } from '../player.component';
import { SkillRollRowComponent } from '../skill-roll-row/skill-roll-row.component';
import { ForgeButtonDirective } from '../../../shared/ui';

@Component({
  selector: 'app-ability-skill-group',
  standalone: true,
  imports: [CommonModule, SkillRollRowComponent, ForgeButtonDirective],
  templateUrl: './ability-skill-group.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AbilitySkillGroupComponent {
  @Input() attr = '';
  @Input() attrName = '';
  @Input() modifier = '+0';
  @Input() open = false;
  @Input() skills: SkillDefinition[] = [];
  @Input() isProficient!: (skillName: string) => boolean;
  @Input() getSkillModString!: (skill: SkillDefinition) => string;

  @Output() toggle = new EventEmitter<string>();
  @Output() rollAbility = new EventEmitter<string>();
  @Output() rollSkill = new EventEmitter<SkillDefinition>();

  glyphFor(attr: string): string {
    const glyphs: Record<string, string> = {
      STR: '✊',
      DEX: '⚔',
      INT: '📘',
      WIS: '✦',
      CHA: '◆',
    };
    return glyphs[attr] || '◆';
  }
}
