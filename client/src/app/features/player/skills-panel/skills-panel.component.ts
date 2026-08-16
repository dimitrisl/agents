import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import type { SkillDefinition } from '../player.component';
import { AbilitySkillGroupComponent } from '../ability-skill-group/ability-skill-group.component';
import { ForgeInputDirective, ForgeToggleComponent } from '../../../shared/ui';

@Component({
  selector: 'app-skills-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, AbilitySkillGroupComponent, ForgeInputDirective, ForgeToggleComponent],
  templateUrl: './skills-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkillsPanelComponent {
  @Input() showProficientOnly = false;
  @Input() openGroups: { [key: string]: boolean } = {};
  @Input() attributes: string[] = [];
  @Input() getSkillsByAttribute!: (attr: string) => SkillDefinition[];
  @Input() getAttributeFullName!: (attr: string) => string;
  @Input() getAttributeModifier!: (attr: string) => string;
  @Input() isProficient!: (skillName: string) => boolean;
  @Input() getSkillModString!: (skill: SkillDefinition) => string;

  @Output() showProficientOnlyChange = new EventEmitter<boolean>();
  @Output() toggleGroup = new EventEmitter<string>();
  @Output() rollAbility = new EventEmitter<string>();
  @Output() rollSkill = new EventEmitter<SkillDefinition>();

  searchTerm = '';

  visibleSkills(attr: string): SkillDefinition[] {
    const term = this.searchTerm.trim().toLowerCase();
    return this.getSkillsByAttribute(attr).filter((skill) => {
      const proficiencyMatch = !this.showProficientOnly || this.isProficient(skill.name);
      const searchMatch = !term || skill.name.toLowerCase().includes(term);
      return proficiencyMatch && searchMatch;
    });
  }
}
