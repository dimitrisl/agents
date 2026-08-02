import { Injectable } from '@angular/core';

export type RollMode = 'normal' | 'advantage' | 'disadvantage';

export interface DiceRoll {
  /** Human readable form, e.g. `1d20 (17) +5`. */
  expression: string;
  numDice: number;
  sides: number;
  modifier: number;
  /** Every die that was actually thrown — both d20s under advantage/disadvantage. */
  rolls: number[];
  /** The value that counts: the kept d20, or the sum of the dice. */
  raw: number;
  total: number;
  /** The mode that was actually applied, not the one that was asked for. */
  mode: RollMode;
  isNat20: boolean;
  isNat1: boolean;
}

export interface RollOptions {
  sides: number;
  numDice?: number;
  modifier?: number;
  mode?: RollMode;
}

/** One named line of a damage roll — the weapon, then every rider stacked on it. */
export interface DamagePart {
  label: string;
  /** `1d8+4 slashing`, `5d6`, `+2` — whatever shape the sheet or the rules gave us. */
  notation: string;
  /** Set for dice a critical hit must not double, such as Brutal Critical's own dice. */
  noCrit?: boolean;
}

export interface DamagePartResult {
  label: string;
  numDice: number;
  sides: number;
  rolls: number[];
  modifier: number;
  total: number;
}

export interface DamageRoll {
  parts: DamagePartResult[];
  /** `Longsword 1d8 (5) +4 + Sneak Attack 5d6 (18)`. */
  expression: string;
  /** Every die thrown, in part order. */
  rolls: number[];
  total: number;
  crit: boolean;
}

/** Mirrors the backend parser in `backend/services/dice_service.py`. */
const NOTATION = /^(\d*)d(\d+)([+-]\d+)?$/;

/**
 * Lenient form of the above. Weapons arrive from the backend as `1d8 + 4 slashing`
 * (see `rebuild_damage_formula`), so the trailing damage type and the spaces have
 * to survive parsing, and several modifiers may be chained.
 */
const LOOSE_NOTATION = /^(\d*)d(\d+)((?:[+-]\d+)*)/;
const FLAT_NOTATION = /^([+-]?\d+)/;

/**
 * Every die in the app is thrown here.
 *
 * Keeping this in one place is what stops the rules from drifting apart: before
 * this service the player sheet honoured advantage while the DM screen and the
 * quick roller silently ignored it.
 */
@Injectable({ providedIn: 'root' })
export class DiceService {
  /**
   * A single uniform die in `1..sides` — the only source of randomness for dice
   * in the client. Swap the generator here and every roll follows.
   */
  rollDie(sides: number): number {
    return Math.floor(Math.random() * sides) + 1;
  }

  roll({ sides, numDice = 1, modifier = 0, mode = 'normal' }: RollOptions): DiceRoll {
    // Advantage is a d20 mechanic: it has no meaning on 2d6, so it is dropped
    // rather than silently applied to the wrong thing.
    const modeApplies = mode !== 'normal' && sides === 20 && numDice === 1;
    const effectiveMode: RollMode = modeApplies ? mode : 'normal';

    let rolls: number[];
    let raw: number;

    if (modeApplies) {
      rolls = [this.rollDie(20), this.rollDie(20)];
      raw = mode === 'advantage' ? Math.max(...rolls) : Math.min(...rolls);
    } else {
      rolls = Array.from({ length: numDice }, () => this.rollDie(sides));
      raw = rolls.reduce((sum, value) => sum + value, 0);
    }

    return {
      expression: this.format(numDice, sides, raw, modifier),
      numDice,
      sides,
      modifier,
      rolls,
      raw,
      total: raw + modifier,
      mode: effectiveMode,
      isNat20: sides === 20 && raw === 20,
      isNat1: sides === 20 && raw === 1,
    };
  }

  /** Convenience for the most common roll in the game. */
  rollD20(modifier = 0, mode: RollMode = 'normal'): DiceRoll {
    return this.roll({ sides: 20, numDice: 1, modifier, mode });
  }

  /** Rolls dice notation (`2d6+1`, `d8`). Falls back to 1d20 like the backend. */
  rollNotation(notation: string, mode: RollMode = 'normal'): DiceRoll {
    const clean = (notation || '1d20').toLowerCase().trim().replace(/\s+/g, '');
    const match = NOTATION.exec(clean);

    if (!match) {
      return this.roll({ sides: 20, numDice: 1, modifier: 0, mode });
    }

    return this.roll({
      numDice: match[1] ? parseInt(match[1], 10) : 1,
      sides: parseInt(match[2], 10),
      modifier: match[3] ? parseInt(match[3], 10) : 0,
      mode,
    });
  }

  /**
   * Reads the dice shapes the sheet actually stores. Returns `numDice: 0` for a
   * flat bonus like Rage's `+2`, which is a real damage part with no dice.
   */
  parseNotation(notation: string): { numDice: number; sides: number; modifier: number } | null {
    const clean = (notation || '').toLowerCase().replace(/\s+/g, '');
    if (!clean) return null;

    const dice = LOOSE_NOTATION.exec(clean);
    if (dice) {
      return {
        numDice: dice[1] ? parseInt(dice[1], 10) : 1,
        sides: parseInt(dice[2], 10),
        modifier: this.sumModifiers(dice[3]),
      };
    }

    const flat = FLAT_NOTATION.exec(clean);
    return flat ? { numDice: 0, sides: 0, modifier: parseInt(flat[1], 10) } : null;
  }

  /**
   * Rolls a weapon and everything riding along with it in one throw, so the player
   * sees `1d8+4 + 5d6` as a single number instead of chaining three separate rolls.
   *
   * A critical hit doubles the dice and leaves the flat modifiers alone, which is
   * why parts carry their bonus separately rather than pre-summed.
   */
  rollDamage(parts: DamagePart[], { crit = false }: { crit?: boolean } = {}): DamageRoll {
    const results: DamagePartResult[] = [];

    for (const part of parts) {
      const parsed = this.parseNotation(part.notation);
      if (!parsed) continue;

      const numDice = crit && !part.noCrit ? parsed.numDice * 2 : parsed.numDice;
      const rolls = Array.from({ length: numDice }, () => this.rollDie(parsed.sides));
      const raw = rolls.reduce((sum, value) => sum + value, 0);

      results.push({
        label: part.label,
        numDice,
        sides: parsed.sides,
        rolls,
        modifier: parsed.modifier,
        total: raw + parsed.modifier,
      });
    }

    return {
      parts: results,
      expression: results.map((part) => this.describePart(part)).join('  +  '),
      rolls: results.flatMap((part) => part.rolls),
      total: results.reduce((sum, part) => sum + part.total, 0),
      crit,
    };
  }

  /** One 4d6-drop-lowest ability score. */
  rollAbilityScore(): number {
    const dice = Array.from({ length: 4 }, () => this.rollDie(6)).sort((a, b) => a - b);
    return dice[1] + dice[2] + dice[3];
  }

  /** A full stat line, highest first. */
  rollAbilityScores(count = 6): number[] {
    return Array.from({ length: count }, () => this.rollAbilityScore()).sort((a, b) => b - a);
  }

  /** ` (ADVANTAGE)` etc., for roll titles. Empty on a normal roll. */
  modeLabel(mode: RollMode): string {
    return mode === 'normal' ? '' : ` (${mode.toUpperCase()})`;
  }

  signed(value: number): string {
    return value >= 0 ? `+${value}` : `${value}`;
  }

  private format(numDice: number, sides: number, raw: number, modifier: number): string {
    return `${numDice}d${sides} (${raw}) ${this.signed(modifier)}`;
  }

  private sumModifiers(chain: string): number {
    return (chain.match(/[+-]\d+/g) ?? []).reduce((sum, value) => sum + parseInt(value, 10), 0);
  }

  private describePart(part: DamagePartResult): string {
    const dice = part.numDice > 0 ? `${part.numDice}d${part.sides} (${part.rolls.join('+')})` : '';
    const modifier = part.modifier !== 0 ? this.signed(part.modifier) : '';
    return [part.label, dice, modifier].filter(Boolean).join(' ');
  }
}
