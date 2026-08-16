import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema, EquipmentItem, Weapon } from '../../../../core/models/character.model';
import { DamagePart, DiceService, RollMode } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';
import {
  ClassCombatAction,
  ClassCombatService,
  CombatProfile,
} from '../../../../core/services/class-combat.service';
import {
  ForgeBadgeComponent,
  ForgeButtonDirective,
  ForgeInputDirective,
} from '../../../../shared/ui';
import { CombatDicePanelComponent } from './combat-dice-panel/combat-dice-panel.component';

const EMPTY_PROFILE: CombatProfile = {
  actions: [],
  extraCritDice: 0,
  critThreshold: 20,
  cantripTier: 1,
};

@Component({
  selector: 'app-combat-panel',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    ForgeBadgeComponent,
    ForgeButtonDirective,
    ForgeInputDirective,
    CombatDicePanelComponent,
  ],
  templateUrl: './combat-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class CombatPanelComponent implements OnChanges {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() rollMode: RollMode = 'normal';

  @Output() addWeapon = new EventEmitter<void>();
  @Output() deleteWeapon = new EventEmitter<number>();
  @Output() toggleEquipped = new EventEmitter<EquipmentItem>();
  @Output() addEquipment = new EventEmitter<void>();
  @Output() deleteEquipment = new EventEmitter<number>();
  @Output() save = new EventEmitter<void>();

  private readonly dice = inject(DiceService);
  private readonly rollToast = inject(RollToastService);
  private readonly classCombat = inject(ClassCombatService);

  profile: CombatProfile = EMPTY_PROFILE;
  riders: ClassCombatAction[] = [];

  /** Riders the player has switched on; they ride along with every damage roll. */
  private readonly activeRiderIds = new Set<string>();
  /** Which notation a multi-option rider is set to, e.g. the Divine Smite slot. */
  private readonly chosenOption: Record<string, string> = {};

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['char']) return;

    this.profile = this.char ? this.classCombat.getProfile(this.char) : EMPTY_PROFILE;
    this.riders = this.classCombat.ridersOf(this.profile);

    // A rider from the previous character must not linger on the new one.
    const known = new Set(this.riders.map((rider) => rider.id));
    for (const id of [...this.activeRiderIds]) {
      if (!known.has(id)) this.activeRiderIds.delete(id);
    }
  }

  // ------------------------------------------------------------------ riders //

  isRiderActive(rider: ClassCombatAction): boolean {
    return this.activeRiderIds.has(rider.id);
  }

  toggleRider(rider: ClassCombatAction): void {
    if (!this.activeRiderIds.delete(rider.id)) {
      this.activeRiderIds.add(rider.id);
    }
  }

  /** The notation a rider contributes right now, honouring its selected option. */
  riderNotation(rider: ClassCombatAction): string {
    return this.chosenOption[rider.id] ?? rider.notation;
  }

  selectOption(rider: ClassCombatAction, notation: string): void {
    this.chosenOption[rider.id] = notation;
    this.activeRiderIds.add(rider.id);
  }

  isOptionSelected(rider: ClassCombatAction, notation: string): boolean {
    return this.riderNotation(rider) === notation;
  }

  get activeRiders(): ClassCombatAction[] {
    return this.riders.filter((rider) => this.activeRiderIds.has(rider.id));
  }

  // ----------------------------------------------------------------- weapons //

  weaponProperties(weapon: Weapon): string[] {
    return (weapon.properties || '')
      .split(',')
      .map((property) => property.trim())
      .filter(Boolean);
  }

  /** `1d8+4` — the weapon's dice normalised, with the bonus folded in exactly once. */
  weaponNotation(weapon: Weapon): string {
    const source = weapon.damage_dice || weapon.damage || '1d4';
    const parsed = this.dice.parseNotation(source);
    if (!parsed || parsed.numDice === 0) return source;

    // The sheet stores the bonus either baked into `damage_dice` or beside it.
    const bonus =
      parsed.modifier !== 0
        ? parsed.modifier
        : (this.dice.parseNotation(weapon.damage_bonus || '')?.modifier ?? 0);

    return `${parsed.numDice}d${parsed.sides}${bonus !== 0 ? this.dice.signed(bonus) : ''}`;
  }

  /** The trailing `slashing` / `piercing` the backend appends to the dice string. */
  weaponDamageType(weapon: Weapon): string {
    const match = /\d\s*([a-zA-Z][a-zA-Z ]*)$/.exec(weapon.damage_dice || weapon.damage || '');
    return match ? match[1].trim() : '';
  }

  /** What the Damage button will actually throw, riders included. */
  damagePreview(weapon: Weapon): string {
    return [this.weaponNotation(weapon), ...this.activeRiders.map((r) => this.riderNotation(r))]
      .join(' + ')
      .replace(/\+ \+/g, '+');
  }

  rollAttack(weapon: Weapon): void {
    const roll = this.dice.rollD20(this.attackBonus(weapon), this.rollMode);
    const isCrit = roll.raw >= this.profile.critThreshold;
    const critNote = isCrit && !roll.isNat20 ? ' — CRITICAL' : '';

    this.rollToast.showRoll({
      title: `⚔️ ${weapon.name.toUpperCase()} ATTACK${this.dice.modeLabel(roll.mode)}${critNote}`,
      expression: roll.expression,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: roll.sides,
      modifier: roll.modifier,
      total: roll.total,
      mode: roll.mode,
    });
  }

  rollWeaponDamage(weapon: Weapon, crit = false): void {
    const damage = this.dice.rollDamage(this.damageParts(weapon, crit), { crit });
    const title = crit ? `💥 ${weapon.name.toUpperCase()} CRIT` : `🩸 ${weapon.name.toUpperCase()} DAMAGE`;

    this.showDamage(title, damage);
  }

  // ------------------------------------------------------------ class actions //

  rollClassAction(action: ClassCombatAction): void {
    const notation = this.chosenOption[action.id] ?? action.notation;
    const damage = this.dice.rollDamage([{ label: action.name, notation }]);

    this.showDamage(`${action.icon} ${action.name.toUpperCase()}`, damage);
  }

  // ------------------------------------------------------------------ helpers //

  private damageParts(weapon: Weapon, crit: boolean): DamagePart[] {
    const weaponNotation = this.weaponNotation(weapon);
    const parts: DamagePart[] = [{ label: weapon.name, notation: weaponNotation }];

    for (const rider of this.activeRiders) {
      parts.push({ label: rider.name, notation: this.riderNotation(rider) });
    }

    // Brutal Critical adds weapon dice on top of the doubling, and is not itself doubled.
    if (crit && this.profile.extraCritDice > 0) {
      const sides = this.dice.parseNotation(weaponNotation)?.sides;
      if (sides) {
        parts.push({
          label: 'Brutal Critical',
          notation: `${this.profile.extraCritDice}d${sides}`,
          noCrit: true,
        });
      }
    }

    return parts;
  }

  private showDamage(title: string, damage: ReturnType<DiceService['rollDamage']>): void {
    // The 3D dice can only render one shape, so the part contributing the most
    // dice sets it; the expression carries the exact per-part breakdown.
    const dominant = damage.parts.reduce(
      (best, part) => (part.numDice > (best?.numDice ?? 0) ? part : best),
      damage.parts[0]
    );

    this.rollToast.showRoll({
      title,
      expression: damage.expression,
      raw: damage.rolls.reduce((sum, value) => sum + value, 0),
      rolls: damage.rolls.length > 0 ? damage.rolls : [0],
      sides: dominant?.sides || 6,
      modifier: damage.total - damage.rolls.reduce((sum, value) => sum + value, 0),
      total: damage.total,
      mode: 'normal',
    });
  }

  private attackBonus(weapon: Weapon): number {
    return this.dice.parseNotation(weapon.attack_bonus || '')?.modifier ?? 0;
  }
}
