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
import { CharacterSchema, EquipmentItem, Weapon, WeaponEffect } from '../../../../core/models/character.model';
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
  ForgeIconComponent,
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

type EquipmentFilter = 'all' | 'equipped' | 'attuned' | 'inventory';

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
  ForgeIconComponent,
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

  /** What the last combat-profile request was for; see profileKey(). */
  private profileKey?: string;

  ngOnChanges(changes: SimpleChanges): void {
    if (!changes['char']) return;

    if (!this.char) {
      this.profileSub?.unsubscribe();
      this.profileKey = undefined;
      this.profile = EMPTY_PROFILE;
      this.riders = [];
      this.cdr.markForCheck();
      return;
    }

    // Every save hands us a new character object. Only refetch when something the
    // profile depends on changed: refetching on each save burned through the API
    // rate limit, and a failed request used to wipe Sneak Attack & co.
    const key = this.computeProfileKey(this.char);
    if (key === this.profileKey) {
      this.applyProfile(this.profile);
      return;
    }
    this.profileKey = key;

    this.profileSub?.unsubscribe();
    this.profileSub = this.classCombat.getProfile(this.char).subscribe({
      next: (profile) => this.applyProfile(profile),
      error: (err) => {
        console.warn('Combat profile unavailable; keeping the last known one.', err);
        // Keep the riders already shown; retry on the next change.
        this.profileKey = undefined;
        if (this.profile === EMPTY_PROFILE) {
          this.applyProfile(this.classCombat.fallbackProfile(this.char));
        }
      },
    });
  }

  private computeProfileKey(char: CharacterSchema): string {
    return JSON.stringify([
      char.char_class,
      char.subclass,
      char.char_level,
      char.dnd_edition,
      char.classes,
      char.stats?.CON,
    ]);
  }

  private applyProfile(profile: CombatProfile): void {
    this.profile = profile;
    // Re-derived on every change: riders such as Hunter's Mark depend on known spells.
    this.riders = this.classCombat.ridersOf(this.profile, this.char);

    const known = new Set(this.riders.map((rider) => rider.id));
    for (const id of Array.from(this.activeRiderIds)) {
      if (!known.has(id)) this.activeRiderIds.delete(id);
    }

    this.cdr.markForCheck();
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

  // ------------------------------------------------------- weapon effects //

  /**
   * Switched-on situational effects, keyed by weapon + label so the choice
   * survives the character object being replaced by a save response.
   */
  private readonly activeEffectKeys = new Set<string>();

  private effectKey(weapon: Weapon, effect: WeaponEffect): string {
    return `${weapon.name}|${effect.label}`;
  }

  /** Effects that change a roll; note-only effects are just shown on the card. */
  isEffectRollable(effect: WeaponEffect): boolean {
    return !!(effect.dice?.trim() || effect.damage_bonus || effect.attack_bonus);
  }

  isEffectActive(weapon: Weapon, effect: WeaponEffect): boolean {
    return this.activeEffectKeys.has(this.effectKey(weapon, effect));
  }

  toggleEffect(weapon: Weapon, effect: WeaponEffect): void {
    const key = this.effectKey(weapon, effect);
    if (!this.activeEffectKeys.delete(key)) {
      this.activeEffectKeys.add(key);
    }
  }

  /**
   * Whether the target can save for half against `effect`, and the DC to show,
   * read from a note on the effect or on a note-only effect with the same name,
   * e.g. "DC 16 CON half damage".
   */
  saveHalfInfo(weapon: Weapon, effect: WeaponEffect): { dc?: string } | null {
    const name = (effect.label || '').trim().toLowerCase();
    const notes = (weapon.conditional_effects || [])
      .filter((e) => e === effect || (!this.isEffectRollable(e) && (e.label || '').trim().toLowerCase() === name))
      .map((e) => e.note || '')
      .join(' ');
    if (!/\bhalf\b/i.test(notes)) return null;
    const dc = /DC\s*(\d+)(?:\s+([A-Za-z]{3}))?/i.exec(notes);
    return { dc: dc ? `DC ${dc[1]}${dc[2] ? ' ' + dc[2].toUpperCase() : ''}` : undefined };
  }

  activeEffects(weapon: Weapon): WeaponEffect[] {
    return (weapon.conditional_effects || []).filter(
      (effect) => this.isEffectRollable(effect) && this.isEffectActive(weapon, effect)
    );
  }

  /** Damage the effect adds, e.g. `1d6+2`, or `+2` for a flat bonus; '' if none. */
  effectDamageNotation(effect: WeaponEffect): string {
    const dice = (effect.dice || '').trim();
    const bonus = effect.damage_bonus || 0;
    if (!dice) return bonus ? this.dice.signed(bonus) : '';
    return `${dice}${bonus ? this.dice.signed(bonus) : ''}`;
  }

  /** Chip text: `+1d6 radiant`, `+2 dmg · +2 hit`. */
  effectSummary(effect: WeaponEffect): string {
    const parts: string[] = [];
    const damage = this.effectDamageNotation(effect);
    if (damage) {
      const signed = /^[+-]/.test(damage) ? damage : `+${damage}`;
      const type = effect.damage_type?.trim() || (effect.dice?.trim() ? '' : 'dmg');
      parts.push(type ? `${signed} ${type}` : signed);
    }
    if (effect.attack_bonus) parts.push(`${this.dice.signed(effect.attack_bonus)} hit`);
    return parts.join(' · ');
  }

  addEffect(weapon: Weapon): void {
    weapon.conditional_effects = [...(weapon.conditional_effects || []), { label: 'vs ', dice: '' }];
  }

  removeEffect(weapon: Weapon, index: number): void {
    const effect = weapon.conditional_effects?.[index];
    if (effect) this.activeEffectKeys.delete(this.effectKey(weapon, effect));
    weapon.conditional_effects = (weapon.conditional_effects || []).filter((_, i) => i !== index);
    this.save.emit();
  }

  onEffectChange(
    weapon: Weapon,
    effect: WeaponEffect,
    field: 'label' | 'dice' | 'damage_type' | 'note' | 'damage_bonus' | 'attack_bonus',
    value: string
  ): void {
    if (field === 'damage_bonus' || field === 'attack_bonus') {
      effect[field] = parseInt(value, 10) || 0;
    } else if (field === 'label') {
      // A renamed effect is a different key; carry its on/off state over.
      const wasActive = this.isEffectActive(weapon, effect);
      this.activeEffectKeys.delete(this.effectKey(weapon, effect));
      effect.label = value;
      if (wasActive) this.activeEffectKeys.add(this.effectKey(weapon, effect));
    } else {
      effect[field] = value;
    }
    this.save.emit();
  }

  // ----------------------------------------------------------------- weapons //

  expandedWeaponIndex: number | null = null;

  toggleWeaponEditor(index: number): void {
    this.expandedWeaponIndex = this.expandedWeaponIndex === index ? null : index;
  }

  getWeaponBreakdown(weapon: Weapon): WeaponBreakdown {
    return calculateWeaponBreakdown(weapon, this.char);
  }

  /** "DEX (+5) + Prof (+4) = +9" -> "DEX (+5) + Prof (+4)": the total is shown big above it. */
  formulaSources(formulaText: string): string {
    return (formulaText || '').replace(/\s*=.*$/, '').trim();
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

  /** Includes switched-on situational attack bonuses, so it matches what Attack rolls. */
  displayedAttackBonus(weapon: Weapon): string {
    return this.dice.signed(this.attackBonus(weapon));
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
    // Half-typed values ("1", "1d") would otherwise be rewritten to the 1d4 fallback
    // mid-keystroke; only commit once the field holds a complete dice expression.
    val = (val || '').trim().toLowerCase();
    if (!/^\d+d\d+$/.test(val)) return;
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
    return [
      this.weaponNotation(weapon),
      ...this.activeEffects(weapon).map((e) => this.effectDamageNotation(e)).filter(Boolean),
      ...this.activeRiders.map((r) => this.riderNotation(r)),
    ]
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

    // Extra dice from an effect are weapon damage dice, so a crit doubles them too.
    for (const effect of this.activeEffects(weapon)) {
      const notation = this.effectDamageNotation(effect);
      if (notation) {
        parts.push({ label: effect.label, notation, saveHalf: this.saveHalfInfo(weapon, effect) ?? undefined });
      }
    }

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
    // Most dice decide the fallback shape; diceSides gives each die its own
    // (a 2d6 + 6d8 crit shows d6s and d8s), in the same order as damage.rolls.
    const dominant = damage.parts.reduce(
      (best, part) => (part.numDice > (best?.numDice ?? 0) ? part : best),
      damage.parts[0]
    );

    this.rollToast.showRoll({
      diceSides: damage.parts.flatMap((part) => part.rolls.map(() => part.sides)),
      isCritHit: damage.crit,
      damageParts: damage.parts.map((part) => ({
        label: part.label,
        detail: this.dice.describePartDice(part),
        total: part.total,
        saveHalf: part.saveHalf,
      })),
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
    const situational = this.activeEffects(weapon).reduce((sum, e) => sum + (e.attack_bonus || 0), 0);
    return this.getWeaponBreakdown(weapon).attack.total + situational;
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
  // Table rule: any number of items may be attuned, but only 3 attuned items can
  // be equipped at once. (RAW 5e caps attunement itself at 3, equipped or not.)
  readonly maxActiveAttunements = 3;

  /** Attuned items that are also equipped — the ones the limit applies to. */
  get attunedCount(): number {
    return (this.char.equipment || []).filter(item => !!item.attuned && !!item.equipped).length;
  }

  private showAttunementLimit(): void {
    this.rollToast.showMessage(
      '🔮 ATTUNEMENT LIMIT',
      `Only ${this.maxActiveAttunements} attuned items can be equipped at a time. Unequip one first.`
    );
  }

  toggleAttuned(item: EquipmentItem) {
    // Attuning an equipped item makes it count; attuning one in the inventory doesn't.
    if (!item.attuned && item.equipped && this.attunedCount >= this.maxActiveAttunements) {
      this.showAttunementLimit();
      return;
    }
    item.attuned = !item.attuned;
    this.save.emit();
  }

  onToggleEquipped(item: EquipmentItem) {
    if (!item.equipped && item.attuned && this.attunedCount >= this.maxActiveAttunements) {
      this.showAttunementLimit();
      return;
    }
    this.toggleEquipped.emit(item);
  }

  // --- Equipment list view (presentation only; rows keep their original index) ---
  equipmentFilter: EquipmentFilter = 'all';
  readonly equipmentFilters: { id: EquipmentFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'equipped', label: 'Equipped' },
    { id: 'attuned', label: 'Attuned' },
    { id: 'inventory', label: 'Inventory' },
  ];

  private matchesFilter(item: EquipmentItem, filter: EquipmentFilter): boolean {
    switch (filter) {
      case 'equipped':
        return !!item.equipped;
      case 'attuned':
        return !!item.attuned;
      case 'inventory':
        return !item.equipped;
      default:
        return true;
    }
  }

  equipmentCount(filter: EquipmentFilter): number {
    return (this.char.equipment || []).filter((item) => this.matchesFilter(item, filter)).length;
  }

  /**
   * "All" shows Equipped first, then the rest of the pack; other filters are a
   * single untitled group. `index` is the item's position in char.equipment, which
   * delete still relies on.
   */
  get equipmentGroups(): { title: string | null; rows: { item: EquipmentItem; index: number }[] }[] {
    const rows = (this.char.equipment || []).map((item, index) => ({ item, index }));
    if (this.equipmentFilter !== 'all') {
      return [{ title: null, rows: rows.filter((r) => this.matchesFilter(r.item, this.equipmentFilter)) }];
    }
    return [
      { title: 'Equipped', rows: rows.filter((r) => r.item.equipped) },
      { title: 'Inventory', rows: rows.filter((r) => !r.item.equipped) },
    ].filter((group) => group.rows.length > 0);
  }

  /**
   * AC from an item the rules catalog doesn't know (homebrew, custom magic items).
   * Below 10 it's a bonus (+2), 10 and up it's the armor's base AC; the server
   * recalculates Armor Class on save.
   */
  /** "+2 AC …" in an item's notes, when the item has no AC of its own yet. */
  acHintFromNotes(item: EquipmentItem): number | null {
    if (item.ac_bonus) return null;
    const match = /\+\s*(\d)\s*AC\b/i.exec(item.description || '');
    return match ? Number(match[1]) : null;
  }

  onItemAcChange(item: EquipmentItem, value: string | number | null) {
    item.ac_bonus = Math.max(0, Math.trunc(Number(value) || 0));
    this.save.emit();
  }

  adjustQuantity(item: EquipmentItem, delta: number, event: Event) {
    event.stopPropagation();
    const currentQty = item.quantity ?? 1;
    const newQty = Math.max(0, currentQty + delta);
    item.quantity = newQty;
    this.save.emit();
  }

  /** "Potion of Healing", "Greater Healing Potion 4d4 + 4", "superior healing potion"… */
  isHealingPotion(item: EquipmentItem): boolean {
    const name = (item.name || '').toLowerCase();
    return name.includes('potion') && name.includes('healing');
  }

  drinkPotion(item: EquipmentItem, event: Event) {
    event.stopPropagation();
    const name = (item.name || '').toLowerCase();

    // Dice written on the sheet win ("Superior healing Potion 8d4 + 8").
    const written = /(\d+d\d+)\s*(?:\+\s*(\d+))?/.exec(name);
    if (written) {
      this.consumePotion.emit({ item, dice: written[1], bonus: Number(written[2] ?? 0), name: item.name });
      return;
    }

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
