import { Injectable } from '@angular/core';
import {
  CombatantCondition,
  DeathSaves,
  EncounterState,
  InitiativeCombatant,
} from '../models/initiative.model';

/**
 * Bumped whenever the stored shape changes. An entry written by an older
 * version is dropped rather than guessed at — a half-understood encounter on
 * the table is worse than an empty tracker.
 */
const STORAGE_VERSION = 1;
const KEY_PREFIX = 'dnd.encounter.v1.';

interface StoredEncounter {
  v: number;
  state: EncounterState;
}

/**
 * Keeps the initiative tracker alive across a refresh, one encounter per
 * campaign.
 *
 * This is browser-local on purpose: the API has no encounter document, so
 * nothing here reaches the players or follows the DM to another machine. Every
 * access is guarded — a browser in private mode, a full quota or a hand-edited
 * entry degrades to "nothing saved", never to a workspace that will not open.
 */
@Injectable({ providedIn: 'root' })
export class EncounterStorageService {
  load(campaignName: string): EncounterState | null {
    if (!campaignName) return null;

    let raw: string | null;
    try {
      raw = localStorage.getItem(this.keyFor(campaignName));
    } catch {
      return null;
    }
    if (!raw) return null;

    try {
      return this.parse(JSON.parse(raw));
    } catch {
      // Not JSON at all. Nothing to salvage and nothing to report — the DM
      // gets an empty tracker, which is the honest reading of "no encounter".
      return null;
    }
  }

  save(campaignName: string, state: EncounterState): void {
    if (!campaignName) return;

    const payload: StoredEncounter = { v: STORAGE_VERSION, state };
    try {
      localStorage.setItem(this.keyFor(campaignName), JSON.stringify(payload));
    } catch {
      // Quota or a storage-less context. The encounter still runs in memory;
      // only its survival across a refresh is lost.
    }
  }

  clear(campaignName: string): void {
    if (!campaignName) return;
    try {
      localStorage.removeItem(this.keyFor(campaignName));
    } catch {
      /* nothing to undo */
    }
  }

  private keyFor(campaignName: string): string {
    return `${KEY_PREFIX}${campaignName}`;
  }

  /**
   * Rebuilds the state field by field. Whatever is in storage is untrusted
   * input, so nothing is spread through unchecked: one malformed combatant
   * discards the entry rather than seeding the tracker with `undefined` HP.
   */
  private parse(input: unknown): EncounterState | null {
    if (!this.isRecord(input) || input['v'] !== STORAGE_VERSION) return null;

    const state = input['state'];
    if (!this.isRecord(state)) return null;

    const round = state['round'];
    const activeCombatantId = state['activeCombatantId'];
    const combatants = state['combatants'];

    if (!this.isCount(round)) return null;
    if (activeCombatantId !== null && typeof activeCombatantId !== 'string') return null;
    if (!Array.isArray(combatants)) return null;

    const parsed: InitiativeCombatant[] = [];
    for (const combatant of combatants) {
      const next = this.parseCombatant(combatant);
      if (!next) return null;
      parsed.push(next);
    }

    // A pointer at a combatant who is not in the list would light up nobody's
    // row while still blocking the first Next Turn.
    const active =
      typeof activeCombatantId === 'string' &&
      parsed.some((combatant) => combatant.id === activeCombatantId)
        ? activeCombatantId
        : null;

    return { round, activeCombatantId: active, combatants: parsed };
  }

  private parseCombatant(input: unknown): InitiativeCombatant | null {
    if (!this.isRecord(input)) return null;

    const id = input['id'];
    const name = input['name'];
    if (typeof id !== 'string' || !id) return null;
    if (typeof name !== 'string' || !name) return null;

    const numbers = ['initiative', 'hp', 'max_hp', 'ac', 'dex'] as const;
    for (const field of numbers) {
      if (!this.isFiniteNumber(input[field])) return null;
    }
    if (typeof input['is_player'] !== 'boolean') return null;

    const conditions = this.parseConditions(input['conditions']);
    if (!conditions) return null;

    const deathSaves = this.parseDeathSaves(input['deathSaves']);
    if (deathSaves === false) return null;

    const combatant: InitiativeCombatant = {
      id,
      name,
      initiative: input['initiative'] as number,
      hp: input['hp'] as number,
      max_hp: input['max_hp'] as number,
      ac: input['ac'] as number,
      dex: input['dex'] as number,
      is_player: input['is_player'] as boolean,
      conditions,
    };

    if (typeof input['portrait'] === 'string') combatant.portrait = input['portrait'];
    if (typeof input['statblock'] === 'string') combatant.statblock = input['statblock'];
    if (deathSaves) combatant.deathSaves = deathSaves;

    return combatant;
  }

  private parseConditions(input: unknown): CombatantCondition[] | null {
    if (input === undefined) return [];
    if (!Array.isArray(input)) return null;

    const conditions: CombatantCondition[] = [];
    for (const entry of input) {
      if (!this.isRecord(entry)) return null;

      const name = entry['name'];
      const expiresAtRound = entry['expiresAtRound'];
      if (typeof name !== 'string' || !name) return null;
      if (expiresAtRound !== null && !this.isCount(expiresAtRound)) return null;

      conditions.push({ name, expiresAtRound });
    }
    return conditions;
  }

  /** `false` is "present but broken"; `null` is "absent", which is legitimate. */
  private parseDeathSaves(input: unknown): DeathSaves | null | false {
    if (input === undefined || input === null) return null;
    if (!this.isRecord(input)) return false;

    const successes = input['successes'];
    const failures = input['failures'];
    if (!this.isCount(successes) || !this.isCount(failures)) return false;

    return { successes, failures };
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }

  private isFiniteNumber(value: unknown): value is number {
    return typeof value === 'number' && Number.isFinite(value);
  }

  /** A non-negative whole number — rounds and tallies never run backwards. */
  private isCount(value: unknown): value is number {
    return this.isFiniteNumber(value) && Number.isInteger(value) && value >= 0;
  }
}
