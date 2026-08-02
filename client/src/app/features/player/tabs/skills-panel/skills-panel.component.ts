import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ForgeBadgeComponent, ForgeButtonDirective, ForgeSectionComponent } from '../../../../shared/ui';
import type { SkillDefinition } from '../../player.component';

@Component({
  selector: 'app-skills-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeSectionComponent,
  ],
  templateUrl: './skills-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkillsPanelComponent {
  @Input() allSkills: SkillDefinition[] = [];
  @Input() isProficient!: (skillName: string) => boolean;
  @Input() getSkillModString!: (skill: SkillDefinition) => string;
  @Input() getAttributeFullName!: (attr: string) => string;

  @Output() rollSkill = new EventEmitter<SkillDefinition>();

  showProficientOnly = false;
  openGroups: { [key: string]: boolean } = {
    STR: true,
    DEX: true,
    INT: false,
    WIS: false,
    CHA: false,
  };

  readonly skillAttributes = ['STR', 'DEX', 'INT', 'WIS', 'CHA'];

  toggleGroup(attr: string): void {
    this.openGroups[attr] = !this.openGroups[attr];
  }

  getSkillsByAttribute(attr: string): SkillDefinition[] {
    return this.allSkills.filter((skill) => skill.ability === attr);
  }
}
