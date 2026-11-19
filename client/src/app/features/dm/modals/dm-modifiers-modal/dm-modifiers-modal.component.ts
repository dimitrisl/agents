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
  ForgeInputDirective,
  ForgeModalComponent,
  ForgeTextareaDirective,
  ForgeToggleComponent,
} from '../../../../shared/ui';
import type { DmModifiers } from '../../../../core/models/character.model';
import type { PartyMember } from '../../../../core/models/party.model';

export interface DmModifiersSaveEvent {
  member: PartyMember;
  exhaustion_level: number;
  exhaustion_bypass: boolean;
  magic_items_suppressed: boolean;
  dm_modifiers: Required<DmModifiers>;
}

const DEFAULT_MODIFIERS = (): Required<DmModifiers> => ({
  attack_bonus: 0,
  damage_bonus: 0,
  ac_bonus: 0,
  speed_bonus: 0,
  hp_max_bonus: 0,
  initiative_bonus: 0,
  saving_throws_bonus: 0,
  ability_checks_bonus: 0,
  spell_save_dc_bonus: 0,
  passive_perception_bonus: 0,
  note: '',
});

@Component({
  selector: 'app-dm-modifiers-modal',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    ForgeModalComponent,
    ForgeTextareaDirective,
    ForgeToggleComponent,
  ],
  templateUrl: './dm-modifiers-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DmModifiersModalComponent implements OnChanges {
  @Input() open = false;
  @Input() member: PartyMember | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() saveModifiers = new EventEmitter<DmModifiersSaveEvent>();

  exhaustionLevel = 0;
  exhaustionBypass = false;
  magicItemsSuppressed = false;
  modifiers: Required<DmModifiers> = DEFAULT_MODIFIERS();

  readonly numericFields: ReadonlyArray<{
    key: Exclude<keyof DmModifiers, 'note'>;
    label: string;
    hint: string;
  }> = [
    { key: 'attack_bonus', label: 'Attack Bonus', hint: 'Weapons & Spell Attacks' },
    { key: 'damage_bonus', label: 'Damage Bonus', hint: 'Weapon Damage Rolls' },
    { key: 'ac_bonus', label: 'Armor Class (AC)', hint: 'Added to AC breakdown' },
    { key: 'speed_bonus', label: 'Speed (ft)', hint: 'Before Exhaustion halving' },
    { key: 'hp_max_bonus', label: 'Max HP', hint: 'Signed adjustment (+ / -)' },
    { key: 'initiative_bonus', label: 'Initiative', hint: 'Added to Dexterity Init' },
    { key: 'saving_throws_bonus', label: 'Saving Throws', hint: 'All 6 saves + Death Saves' },
    { key: 'ability_checks_bonus', label: 'Ability & Skill Checks', hint: 'All abilities, skills & init' },
    { key: 'spell_save_dc_bonus', label: 'Spell Save DC', hint: 'Caster Spell DC offset' },
    { key: 'passive_perception_bonus', label: 'Passive Perception', hint: 'Direct passive offset' },
  ];

  ngOnChanges(changes: SimpleChanges): void {
    if ((changes['member'] || changes['open']) && this.open && this.member) {
      this.exhaustionLevel = Math.max(0, Math.min(6, Number(this.member.exhaustion_level ?? 0)));
      this.exhaustionBypass = !!this.member.exhaustion_bypass;
      this.magicItemsSuppressed = !!this.member.magic_items_suppressed;
      this.modifiers = {
        ...DEFAULT_MODIFIERS(),
        ...(this.member.dm_modifiers || {}),
        note: this.member.dm_modifiers?.note ?? '',
      };
    }
  }

  adjustExhaustion(delta: number): void {
    this.exhaustionLevel = Math.max(0, Math.min(6, this.exhaustionLevel + delta));
  }

  resetModifiers(): void {
    this.modifiers = DEFAULT_MODIFIERS();
    this.exhaustionBypass = false;
    this.magicItemsSuppressed = false;
  }

  submit(): void {
    if (!this.member) return;
    const cleanMods = DEFAULT_MODIFIERS();
    for (const f of this.numericFields) {
      const parsed = Math.trunc(Number(this.modifiers[f.key] ?? 0)) || 0;
      cleanMods[f.key] = parsed;
    }
    cleanMods.note = String(this.modifiers.note || '').slice(0, 500);

    this.saveModifiers.emit({
      member: this.member,
      exhaustion_level: this.exhaustionLevel,
      exhaustion_bypass: this.exhaustionBypass,
      magic_items_suppressed: this.magicItemsSuppressed,
      dm_modifiers: cleanMods,
    });
  }
}
