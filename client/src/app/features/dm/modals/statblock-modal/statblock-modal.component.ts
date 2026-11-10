import { ChangeDetectionStrategy, Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ForgeButtonDirective, ForgeModalComponent } from '../../../../shared/ui';
import type { InitiativeCombatant } from '../../../../core/models/initiative.model';
import type { PartyMember } from '../../../../core/models/party.model';
import type { MonsterAction } from '../../../../core/models/bestiary.model';
import { DiceService } from '../../../../core/services/dice.service';
import { RollToastService } from '../../../../core/services/roll-toast.service';

const DND_DAMAGE_TYPES = [
  'acid',
  'bludgeoning',
  'cold',
  'fire',
  'force',
  'lightning',
  'necrotic',
  'piercing',
  'poison',
  'psychic',
  'radiant',
  'slashing',
  'thunder',
];

const DAMAGE_TYPE_REGEX = new RegExp('\\b(' + DND_DAMAGE_TYPES.join('|') + ')(?:\\s+damage)?\\b', 'i');

@Component({
  selector: 'app-statblock-modal',
  standalone: true,
  imports: [CommonModule, ForgeButtonDirective, ForgeModalComponent],
  templateUrl: './statblock-modal.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class StatblockModalComponent {
  @Input() open = false;
  @Input() combatant: InitiativeCombatant | null = null;
  @Input() partyMember: PartyMember | null = null;

  @Output() openChange = new EventEmitter<boolean>();
  @Output() closed = new EventEmitter<void>();
  @Output() viewBeyond = new EventEmitter<string>();

  constructor(
    public dice: DiceService,
    public rollToast: RollToastService,
  ) {}

  hasStructuredContent(): boolean {
    if (!this.combatant) return false;
    const hasActions = Array.isArray(this.combatant.actions) && this.combatant.actions.length > 0;
    const hasTraits = Array.isArray(this.combatant.traits) && this.combatant.traits.length > 0;
    const hasStats = !!this.combatant.stats;
    return hasActions || hasTraits || hasStats;
  }

  abilityMod(score?: number | null): string {
    const s = score ?? 10;
    const mod = Math.floor((s - 10) / 2);
    return this.formatBonus(mod);
  }

  formatBonus(bonus: number): string {
    return bonus >= 0 ? `+${bonus}` : `${bonus}`;
  }

  getActionAttackBonus(action: MonsterAction): number | null {
    if (action.attack_bonus !== undefined && action.attack_bonus !== null) {
      const num = Number(action.attack_bonus);
      if (!isNaN(num)) return num;
    }
    const text = action.description || action.desc || '';
    if (!text) return null;
    const match = /([+-]?\s*\d+)\s+to\s+hit/i.exec(text);
    if (match) {
      const parsed = parseInt(match[1].replace(/\s+/g, ''), 10);
      return isNaN(parsed) ? null : parsed;
    }
    return null;
  }

  getActionDamageDice(action: MonsterAction): string | null {
    if (action.damage_dice !== undefined && action.damage_dice !== null) {
      const str = String(action.damage_dice).trim().replace(/\s+/g, '');
      if (str.length > 0) return str;
    }
    const text = action.description || action.desc || '';
    if (!text) return null;

    // 1. Parenthesized dice expression after Hit:, taking, takes, or saving throw
    const parenMatch = /(?:Hit:|taking|takes|or|takes\s+an?)\s*.*?\(\s*(\d+d\d+(?:\s*[+-]\s*\d+)?)\s*\)/i.exec(text);
    if (parenMatch) {
      return parenMatch[1].replace(/\s+/g, '');
    }

    // 2. Any general parenthesized dice notation
    const anyParen = /\(\s*(\d+d\d+(?:\s*[+-]\s*\d+)?)\s*\)/i.exec(text);
    if (anyParen) {
      return anyParen[1].replace(/\s+/g, '');
    }

    // 3. Unparenthesized dice expression followed by damage type or damage
    const directDice = /(\d+d\d+(?:\s*[+-]\s*\d+)?)\s*(?:[a-z]+\s+)?damage/i.exec(text);
    if (directDice) {
      return directDice[1].replace(/\s+/g, '');
    }

    // 4. Flat integer damage (e.g. Hit: 1 slashing damage)
    const flatMatch = /Hit:\s*(\d+)\s+[a-z]+\s+damage/i.exec(text);
    if (flatMatch) {
      return flatMatch[1].trim();
    }

    return null;
  }

  getActionDamageType(action: MonsterAction): string | null {
    if (action.damage_type !== undefined && action.damage_type !== null) {
      const str = String(action.damage_type).trim().toLowerCase();
      if (str.length > 0) return str;
    }
    const text = action.description || action.desc || '';
    if (!text) return null;

    const hitIndex = text.search(/Hit:|taking|takes|or/i);
    const searchSection = hitIndex >= 0 ? text.slice(hitIndex) : text;
    const match = searchSection.match(DAMAGE_TYPE_REGEX);
    return match ? match[1].toLowerCase() : null;
  }

  rollAttack(action: MonsterAction): void {
    if (!this.combatant) return;
    const bonus = this.getActionAttackBonus(action);
    if (bonus === null) return;

    const roll = this.dice.rollD20(bonus);
    const creatureName = (this.combatant.name || 'CREATURE').toUpperCase();
    const actionName = (action.name || 'ATTACK').toUpperCase();

    this.rollToast.showRoll({
      title: `⚔️ ${creatureName} — ${actionName} ATTACK`,
      expression: roll.expression,
      raw: roll.raw,
      rolls: roll.rolls,
      sides: roll.sides,
      modifier: roll.modifier,
      total: roll.total,
      mode: roll.mode,
    });
  }

  rollDamage(action: MonsterAction): void {
    if (!this.combatant) return;
    const damageDice = this.getActionDamageDice(action);
    if (!damageDice) return;

    const damageType = action.damage_type || this.getActionDamageType(action);
    const label = damageType ? `${action.name} (${damageType})` : action.name;
    const damage = this.dice.rollDamage([{ label, notation: damageDice }]);

    const creatureName = (this.combatant.name || 'CREATURE').toUpperCase();
    const actionName = (action.name || 'ACTION').toUpperCase();
    const dominant = damage.parts.reduce(
      (best, part) => (part.numDice > (best?.numDice ?? 0) ? part : best),
      damage.parts[0]
    );
    const rawSum = damage.rolls.reduce((sum, value) => sum + value, 0);

    this.rollToast.showRoll({
      title: `💥 ${creatureName} — ${actionName} DAMAGE`,
      expression: damage.expression,
      raw: rawSum,
      rolls: damage.rolls.length > 0 ? damage.rolls : [damage.total],
      sides: dominant?.sides || 6,
      modifier: damage.total - rawSum,
      total: damage.total,
      mode: 'normal',
      diceSides: damage.parts.flatMap((p) => p.rolls.map(() => p.sides)),
      isCritHit: damage.crit,
      damageParts: damage.parts.map((p) => ({
        label: p.label,
        detail: this.dice.describePartDice(p),
        total: p.total,
        saveHalf: p.saveHalf,
      })),
    });
  }
}
