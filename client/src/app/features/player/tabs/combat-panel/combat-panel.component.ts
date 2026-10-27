import { Subscription } from 'rxjs';
import {
  ChangeDetectionStrategy,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  Output,
  SimpleChanges,
  inject,
  ChangeDetectorRef,
  OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { CharacterSchema, EquipmentItem, Weapon } from '../../../../core/models/character.model';
import { getMasteryDefinition, calculateToppleDc } from '../../../../core/rules/weapon-masteries';
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
  ForgeModalComponent,
  ForgeSelectDirective,
} from '../../../../shared/ui';
import { CombatDicePanelComponent } from './combat-dice-panel/combat-dice-panel.component';
import {
  calculateWeaponBreakdown,
  extractMagicBonus,
  WeaponBreakdown,
} from '../../../../core/rules/weapon-calc';

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
    ForgeModalComponent,
    ForgeSelectDirective,
    CombatDicePanelComponent,
  ],
  templateUrl: './combat-panel.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    class: 'block',
  },
})
export class CombatPanelComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) char!: CharacterSchema;
  @Input() editMode = false;
  @Input() rollMode: RollMode = 'normal';
  @Input() encounterState: any = null;

  @Output() addWeapon = new EventEmitter<void>();
  @Output() deleteWeapon = new EventEmitter<number>();
  @Output() toggleEquipped = new EventEmitter<EquipmentItem>();
  @Output() addEquipment = new EventEmitter<void>();
  @Output() deleteEquipment = new EventEmitter<number>();
  @Output() save = new EventEmitter<void>();
  @Output() consumePotion = new EventEmitter<{ item: EquipmentItem; dice: string; bonus: number; name: string }>();

  showCoinModal = false;
  selectedCoin: 'cp' | 'sp' | 'ep' | 'gp' | 'pp' = 'gp';
  readonly coinTypes: ('pp' | 'gp' | 'ep' | 'sp' | 'cp')[] = ['pp', 'gp', 'ep', 'sp', 'cp'];
  coinNumpadValue = '0';

  selectCoin(c: 'pp' | 'gp' | 'ep' | 'sp' | 'cp') {
    this.selectedCoin = c;
  }

  private readonly dice = inject(DiceService);
  private readonly rollToast = inject(RollToastService);
  private readonly classCombat = inject(ClassCombatService);
  private readonly cdr = inject(ChangeDetectorRef);

  private profileSub?: Subscription;
  profile: CombatProfile = EMPTY_PROFILE;
  riders: ClassCombatAction[] = [];

  /** Riders the player has switched on; they ride along with every damage roll. */
  private readonly activeRiderIds = new Set<string>();
  /** Which notation a multi-option rider is set to, e.g. the Divine Smite slot. */
  private readonly chosenOption: Record<string, string> = {};

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['char']) return;

    if (this.profileSub) {
      this.profileSub.unsubscribe();
    }

    if (!this.char) {
      this.profile = EMPTY_PROFILE;
      this.riders = [];
      this.cdr.markForCheck();
      return;
    }

    this.profileSub = this.classCombat.getProfile(this.char).subscribe(profile => {
      this.profile = profile;
      this.riders = this.classCombat.ridersOf(this.profile, this.char);

      const known = new Set(this.riders.map((rider) => rider.id));
      for (const id of Array.from(this.activeRiderIds)) {
        if (!known.has(id)) this.activeRiderIds.delete(id);
      }

      this.cdr.markForCheck();
    });
  }

  ngOnDestroy(): void {
    if (this.profileSub) {
      this.profileSub.unsubscribe();
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

  expandedWeaponIndex: number | null = null;

  toggleWeaponEditor(index: number): void {
    this.expandedWeaponIndex = this.expandedWeaponIndex === index ? null : index;
  }

  getWeaponBreakdown(weapon: Weapon): WeaponBreakdown {
    return calculateWeaponBreakdown(weapon, this.char);
  }

  getWeaponMagicBonus(weapon: Weapon): number {
    return extractMagicBonus(weapon);
  }

  getWeaponBaseDice(weapon: Weapon): string {
    const raw = weapon.damage_dice || weapon.damage || '1d4';
    const match = /(\d+d\d+)/.exec(raw);
    return match ? match[1] : '1d4';
  }

  formatMod(score?: number): string {
    const mod = Math.floor(((score ?? 10) - 10) / 2);
    return mod >= 0 ? `+${mod}` : `${mod}`;
  }

  displayedAttackBonus(weapon: Weapon): string {
    const total = this.getWeaponBreakdown(weapon).attack.total;
    return this.dice.signed(total);
  }

  onWeaponAbilityChange(weapon: Weapon, val: string): void {
    weapon.ability_modifier = val || undefined;
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponMagicChange(weapon: Weapon, val: any): void {
    weapon.magic_bonus = parseInt(val, 10) || 0;
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponProficiencyChange(weapon: Weapon, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    weapon.proficient = checked;
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponMiscAttackChange(weapon: Weapon, val: any): void {
    weapon.misc_attack_bonus = parseInt(val, 10) || 0;
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponMiscDamageChange(weapon: Weapon, val: any): void {
    weapon.misc_damage_bonus = parseInt(val, 10) || 0;
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponBaseDiceChange(weapon: Weapon, val: string): void {
    const bd = this.getWeaponBreakdown(weapon);
    const type = weapon.damage_type || bd.damage.damageType;
    const bonus = bd.damage.totalBonus;
    const bonusStr = bonus !== 0 ? (bonus > 0 ? `+${bonus}` : `${bonus}`) : '';
    weapon.damage_dice = `${val}${bonusStr} ${type}`.trim();
    this.syncWeaponCalculations(weapon, false);
  }

  onWeaponDamageTypeChange(weapon: Weapon, val: string): void {
    weapon.damage_type = val;
    this.syncWeaponCalculations(weapon, false);
  }

  onManualAttackBonusChange(weapon: Weapon): void {
    const parsed = this.dice.parseNotation(weapon.attack_bonus || '');
    if (parsed) {
      const target = parsed.modifier;
      const base = calculateWeaponBreakdown({ ...weapon, misc_attack_bonus: 0 }, this.char);
      weapon.misc_attack_bonus = target - base.attack.total;
    }
    this.syncWeaponCalculations(weapon, false);
  }

  onManualDamageDiceChange(weapon: Weapon): void {
    const parsed = this.dice.parseNotation(weapon.damage_dice || '');
    if (parsed) {
      const targetBonus = parsed.modifier;
      const base = calculateWeaponBreakdown({ ...weapon, misc_damage_bonus: 0 }, this.char);
      weapon.misc_damage_bonus = targetBonus - base.damage.totalBonus;
    }
    this.syncWeaponCalculations(weapon, false);
  }

  syncWeaponCalculations(weapon: Weapon, showToast = true): void {
    const bd = this.getWeaponBreakdown(weapon);
    weapon.attack_bonus = this.dice.signed(bd.attack.total);
    weapon.damage_dice = `${bd.damage.notation} ${bd.damage.damageType}`.trim();
    weapon.damage_bonus = this.dice.signed(bd.damage.totalBonus);
    weapon.magic_bonus = bd.attack.magicBonus;
    this.save.emit();
    if (showToast) {
      this.rollToast.showMessage(
        '⚡ WEAPON SYNCHRONIZED',
        `${weapon.name}: To Hit is ${weapon.attack_bonus}, Damage is ${weapon.damage_dice}`
      );
    }
  }

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
    return this.getWeaponBreakdown(weapon).attack.total;
  }

  isTopple(mastery: string): boolean {
    return (mastery || '').toLowerCase().trim() === 'topple';
  }

  getToppleDc(w?: any): number {
    const stats = this.char.stats || { STR: 10, DEX: 10 };
    const strMod = Math.floor(((stats.STR ?? 10) - 10) / 2);
    const dexMod = Math.floor(((stats.DEX ?? 10) - 10) / 2);
    const pb = this.char.proficiency_bonus || 2;

    const resolveWeaponMod = (weapon: any): number => {
      if (weapon.ability_modifier !== undefined && weapon.ability_modifier !== null) {
        if (typeof weapon.ability_modifier === 'number') return weapon.ability_modifier;
        const explicit = String(weapon.ability_modifier).toUpperCase().trim();
        if (explicit === 'STR') return strMod;
        if (explicit === 'DEX') return dexMod;
      }
      const props = (weapon.properties || '').toLowerCase();
      const isFinesse = props.includes('finesse');
      const isRanged = (weapon.range || '').includes('/') && !props.includes('thrown');
      if (!isFinesse && !isRanged) {
        return strMod;
      }
      return Math.max(strMod, dexMod);
    };

    if (w) {
      return calculateToppleDc(resolveWeaponMod(w), pb);
    }

    const TOPPLE_WEAPON_NAMES = ['battleaxe', 'lance', 'maul', 'quarterstaff', 'trident'];
    const weapons = this.char.weapons || [];
    const toppleWeapons = weapons.filter((wpn: any) => {
      const name = (wpn.name || '').toLowerCase();
      return (
        (wpn.mastery || '').toLowerCase().trim() === 'topple' ||
        (wpn.properties || '').toLowerCase().includes('topple') ||
        TOPPLE_WEAPON_NAMES.some((tw) => name.includes(tw))
      );
    });
    if (toppleWeapons.length > 0) {
      return Math.max(...toppleWeapons.map((wpn) => calculateToppleDc(resolveWeaponMod(wpn), pb)));
    }

    return calculateToppleDc(strMod, pb);
  }

  getMasteryTrigger(mastery: string): string | null {
    return getMasteryDefinition(mastery)?.trigger || null;
  }

  masteryTooltip(mastery: string, w?: any): string {
    const def = getMasteryDefinition(mastery);
    if (!def) return mastery;
    let text = `${def.name} [Trigger: ${def.trigger}]: ${def.summary} ${def.ruleText}`;
    if (this.isTopple(mastery)) {
      text += ` [DC ${this.getToppleDc(w)} CON Save]`;
    }
    return text;
  }

  // --- Currency & Wallet ---
  get currency() {
    return this.char.currency || { cp: 0, sp: 0, ep: 0, gp: 0, pp: 0 };
  }

  openCoinModal(coin: 'cp' | 'sp' | 'ep' | 'gp' | 'pp' = 'gp') {
    this.selectedCoin = coin;
    this.coinNumpadValue = '0';
    this.showCoinModal = true;
  }

  closeCoinModal() {
    this.showCoinModal = false;
  }

  appendCoinDigit(digit: string) {
    if (this.coinNumpadValue === '0') {
      this.coinNumpadValue = digit;
    } else if (this.coinNumpadValue.length < 6) {
      this.coinNumpadValue += digit;
    }
  }

  backspaceCoin() {
    if (this.coinNumpadValue.length <= 1) {
      this.coinNumpadValue = '0';
    } else {
      this.coinNumpadValue = this.coinNumpadValue.slice(0, -1);
    }
  }

  clearCoinNumpad() {
    this.coinNumpadValue = '0';
  }

  addCoinPill(amount: number) {
    const cur = parseInt(this.coinNumpadValue, 10) || 0;
    this.coinNumpadValue = String(cur + amount);
  }

  executeAddCoins() {
    const amt = parseInt(this.coinNumpadValue, 10) || 0;
    if (amt > 0) {
      if (!this.char.currency) {
        this.char.currency = { cp: 0, sp: 0, ep: 0, gp: 0, pp: 0 };
      }
      this.char.currency[this.selectedCoin] = (this.char.currency[this.selectedCoin] || 0) + amt;
      this.save.emit();
      this.rollToast.showMessage('💰 LOOT ADDED', `Added ${amt} ${this.selectedCoin.toUpperCase()} (Total: ${this.char.currency[this.selectedCoin]}).`);
    }
    this.closeCoinModal();
  }

  executeSpendCoins() {
    const amt = parseInt(this.coinNumpadValue, 10) || 0;
    if (amt > 0) {
      if (!this.char.currency) {
        this.char.currency = { cp: 0, sp: 0, ep: 0, gp: 0, pp: 0 };
      }
      const currentVal = this.char.currency[this.selectedCoin] || 0;
      if (amt > currentVal) {
        this.rollToast.showMessage('⚠️ INSUFFICIENT COINS', `You only have ${currentVal} ${this.selectedCoin.toUpperCase()}.`);
        return;
      }
      this.char.currency[this.selectedCoin] = currentVal - amt;
      this.save.emit();
      this.rollToast.showMessage('🪙 COINS SPENT', `Spent ${amt} ${this.selectedCoin.toUpperCase()} (Remaining: ${this.char.currency[this.selectedCoin]}).`);
    }
    this.closeCoinModal();
  }

  // --- Attunement & Equipment ---
  get attunedCount(): number {
    return (this.char.equipment || []).filter(item => !!item.attuned).length;
  }

  toggleAttuned(item: EquipmentItem) {
    if (!item.attuned && this.attunedCount >= 3) {
      this.rollToast.showMessage('🔮 ATTUNEMENT LIMIT', 'You can only attune up to 3 magic items at a time (5e rules).');
      return;
    }
    item.attuned = !item.attuned;
    this.save.emit();
  }

  adjustQuantity(item: EquipmentItem, delta: number, event: Event) {
    event.stopPropagation();
    const currentQty = item.quantity ?? 1;
    const newQty = Math.max(0, currentQty + delta);
    item.quantity = newQty;
    this.save.emit();
  }

  isHealingPotion(item: EquipmentItem): boolean {
    const name = (item.name || '').toLowerCase();
    return name.includes('potion of') && name.includes('healing');
  }

  drinkPotion(item: EquipmentItem, event: Event) {
    event.stopPropagation();
    const name = (item.name || '').toLowerCase();
    let dice = '2d4';
    let bonus = 2;
    if (name.includes('supreme')) {
      dice = '10d4';
      bonus = 20;
    } else if (name.includes('superior')) {
      dice = '8d4';
      bonus = 8;
    } else if (name.includes('greater')) {
      dice = '4d4';
      bonus = 4;
    }

    this.consumePotion.emit({ item, dice, bonus, name: item.name });
  }
}
