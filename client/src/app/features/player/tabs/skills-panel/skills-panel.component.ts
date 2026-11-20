import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeIconComponent,
  ForgeSectionComponent,
  ForgeToggleComponent,
} from '../../../../shared/ui';
import type { SkillDefinition } from '../../player.component';

export type MobileSkillFilter = 'ALL' | 'PROF' | 'STR' | 'DEX' | 'INT' | 'WIS' | 'CHA';

@Component({
  selector: 'app-skills-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeIconComponent,
    ForgeSectionComponent,
    ForgeToggleComponent,
  ],
  templateUrl: './skills-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SkillsPanelComponent {
  @Input() allSkills: SkillDefinition[] = [];
  @Input() editMode = false;
  @Input() compactMobile = false;
  @Input() passivePerception = 10;
  @Input() passiveInvestigation = 10;
  @Input() passiveInsight = 10;
  @Input() hasCheckDisadvantage = false;
  @Input() hasReliableTalent = false;
  @Input() isProficient!: (skillName: string) => boolean;
  @Input() isExpertise: (skillName: string) => boolean = () => false;
  @Input() getSkillModString!: (skill: SkillDefinition) => string;
  @Input() getAttributeFullName!: (attr: string) => string;

  @Output() rollSkill = new EventEmitter<SkillDefinition>();
  @Output() toggleProficiency = new EventEmitter<string>();
  @Output() toggleExpertise = new EventEmitter<string>();

  mobileSkillFilter = signal<MobileSkillFilter>('ALL');
  readonly mobileFilterOptions: { id: MobileSkillFilter; label: string }[] = [
    { id: 'ALL', label: 'All' },
    { id: 'PROF', label: '★ Proficient' },
    { id: 'STR', label: 'STR' },
    { id: 'DEX', label: 'DEX' },
    { id: 'INT', label: 'INT' },
    { id: 'WIS', label: 'WIS' },
    { id: 'CHA', label: 'CHA' },
  ];

  get totalProficientCount(): number {
    return this.allSkills.filter((skill) => this.isProficient(skill.name)).length;
  }

  get mobileFilteredSkills(): SkillDefinition[] {
    const filter = this.mobileSkillFilter();
    const list = this.allSkills.filter((skill) => {
      if (filter === 'ALL') return true;
      if (filter === 'PROF') return this.isProficient(skill.name);
      return skill.ability === filter;
    });
    return [...list].sort((a, b) => a.name.localeCompare(b.name));
  }

  showProficientOnly = false;
  openGroups: { [key: string]: boolean } = {
    STR: true,
    DEX: true,
    INT: false,
    WIS: false,
    CHA: false,
  };

  readonly skillAttributes = ['STR', 'DEX', 'INT', 'WIS', 'CHA'];

  /** Which groups were open before "Proficient only", restored when it is switched off. */
  private openGroupsBeforeFilter: { [key: string]: boolean } | null = null;

  toggleGroup(attr: string): void {
    this.openGroups = { ...this.openGroups, [attr]: !this.openGroups[attr] };
  }

  get allOpen(): boolean {
    return this.skillAttributes.every((attr) => this.openGroups[attr]);
  }

  /** Expands every group, or collapses them all when every one is already open. */
  toggleAll(): void {
    const open = !this.allOpen;
    this.openGroups = Object.fromEntries(this.skillAttributes.map((attr) => [attr, open]));
  }

  /**
   * On: open exactly the groups that contain a proficient skill and hide the rest.
   * Off: put the groups back the way the player had them.
   */
  setProficientOnly(on: boolean): void {
    this.showProficientOnly = on;
    if (on) {
      this.openGroupsBeforeFilter = { ...this.openGroups };
      this.openGroups = Object.fromEntries(
        this.skillAttributes.map((attr) => [attr, this.proficientCount(attr) > 0])
      );
    } else if (this.openGroupsBeforeFilter) {
      this.openGroups = this.openGroupsBeforeFilter;
      this.openGroupsBeforeFilter = null;
    }
  }

  getSkillsByAttribute(attr: string): SkillDefinition[] {
    return this.allSkills.filter((skill) => skill.ability === attr);
  }

  /** Skills shown in a group under the current filter. */
  visibleSkills(attr: string): SkillDefinition[] {
    const skills = this.getSkillsByAttribute(attr);
    return this.showProficientOnly ? skills.filter((skill) => this.isProficient(skill.name)) : skills;
  }

  proficientCount(attr: string): number {
    return this.getSkillsByAttribute(attr).filter((skill) => this.isProficient(skill.name)).length;
  }
}
