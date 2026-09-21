import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { map, catchError } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { CharacterSchema } from '../models/character.model';
import {
  ClassCombatAction,
  CombatContext,
  CombatProfile,

  critThresholdFor,
  extraCritDiceFor,
  isCaster,

} from '../data/class-combat.data';
import { abilityModifier, hitDieSize, proficiencyBonus } from '../rules';

export function cantripTierFor(level: number): number { return level >= 17 ? 4 : level >= 11 ? 3 : level >= 5 ? 2 : 1; }

export type { ClassCombatAction, CombatProfile } from '../data/class-combat.data';

/**
 * Turns a character sheet into the dice that character actually rolls in combat.
 *
 * A level 10 Rogue gets `Sneak Attack 5d6`, a level 11 Monk a `1d8` Martial Arts
 * die, a level 16 Barbarian `+4` Rage damage — none of which the sheet stores,
 * because all of it is derived from class and level.
 *
 * This is the only place that reads `class-combat.data.ts`. If class progression
 * ever gets served by the API, swap the resolver here and nothing else moves.
 */
@Injectable({ providedIn: 'root' })
export class ClassCombatService {
  buildContext(char: CharacterSchema): CombatContext {
    const stats = char.stats ?? { STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10 };
    const modifier = (score: number) => abilityModifier(score ?? 10);

    return {
      charClass: char.char_class || '',
      subclass: char.subclass || '',
      level: char.char_level || 1,
      is2024: (char.dnd_edition || '2014 Edition').includes('2024'),
      mods: {
        STR: modifier(stats.STR),
        DEX: modifier(stats.DEX),
        CON: modifier(stats.CON),
        INT: modifier(stats.INT),
        WIS: modifier(stats.WIS),
        CHA: modifier(stats.CHA),
      },
      profBonus: proficiencyBonus(char),
    }
  }

  private readonly http = inject(HttpClient);

  getProfile(char: CharacterSchema): Observable<CombatProfile> {
    const ctx = this.buildContext(char);

    if (!ctx.charClass) {
        return of({
            actions: this.universalActions(char, ctx),
            extraCritDice: extraCritDiceFor(ctx),
            critThreshold: critThresholdFor(ctx),
            cantripTier: cantripTierFor(ctx.level),
        });
    }

    const edParam = ctx.is2024 ? '2024 Edition' : '2014 Edition';
    let url = `${environment.apiBaseUrl}/rules/classes/${ctx.charClass.toLowerCase()}/scaling?level=${ctx.level}&edition=${encodeURIComponent(edParam)}`;
    if (ctx.subclass) {
        url += `&subclass=${encodeURIComponent(ctx.subclass)}`;
    }

    return this.http.get<any[]>(url).pipe(
      map(apiActions => {
        // Add icons based on the data if needed, or source
        const mappedActions = apiActions.map(a => ({
          ...a,
          icon: a.icon || '⚔️',
          source: a.source || `${ctx.charClass} ${ctx.level}`
        }));

        return {
          actions: [...mappedActions, ...this.universalActions(char, ctx)],
          extraCritDice: extraCritDiceFor(ctx),
          critThreshold: critThresholdFor(ctx),
          cantripTier: cantripTierFor(ctx.level),
        }
      }),
      catchError(() => {
        return of({
          actions: this.universalActions(char, ctx),
          extraCritDice: extraCritDiceFor(ctx),
          critThreshold: critThresholdFor(ctx),
          cantripTier: cantripTierFor(ctx.level),
        });
      })
    );
  }

  /** The riders a damage roll can stack, in the order they should be offered. */
  ridersOf(profile: CombatProfile): ClassCombatAction[] {
    return profile.actions.filter((action) => action.kind === 'rider');
  }

  /**
   * Rolls every class has: the Hit Die they spend on a short rest, plus the cantrip
   * tier reminder for casters, whose die count is set by character level rather than
   * by the spell.
   */
  private universalActions(char: CharacterSchema, ctx: CombatContext): ClassCombatAction[] {
    const actions: ClassCombatAction[] = [];
    const sides = hitDieSize(char);
    const conMod = ctx.mods.CON;

    actions.push({
      id: 'hit-die',
      name: 'Hit Die',
      icon: '❤️‍🩹',
      kind: 'heal',
      notation: `1d${sides}${conMod >= 0 ? `+${conMod}` : conMod}`,
      hint: 'Spent on a Short Rest to regain hit points.',
      source: `${char.char_class || 'Class'} d${sides}`,
      rollable: true,
    });

    if (isCaster(ctx.charClass)) {
      const tier = cantripTierFor(ctx.level);
      actions.push({
        id: 'cantrip-tier',
        name: 'Cantrip Scaling',
        icon: '✨',
        kind: 'utility',
        notation: `×${tier} dice`,
        hint: 'Damage cantrips gain a die at 5th, 11th and 17th level.',
        source: `Character ${ctx.level}`,
        rollable: false,
      });
    }

    return actions;
  }
}
