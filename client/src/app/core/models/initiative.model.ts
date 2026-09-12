/**
 * A condition riding on a combatant for a number of rounds.
 *
 * The remaining rounds are **derived**, never stored: `expiresAtRound` is an
 * absolute point on the round counter, so stepping the encounter backwards with
 * Previous Turn brings a lapsed condition back exactly as it was. A stored
 * countdown could not — decrementing it on every turn makes the tick
 * irreversible, and a DM correcting a mis-click would silently lose the timer.
 */
export interface CombatantCondition {
  name: string;
  /** The round it lapses at; `null` means it lasts until the DM lifts it. */
  expiresAtRound: number | null;
}

/** A dying player's tally. Three of either ends it. */
export interface DeathSaves {
  successes: number;
  failures: number;
}

export interface InitiativeCombatant {
  id: string;
  /**
   * The party member this row stands for, when it is a hero rather than a
   * monster. It is what keeps the two tabs describing the same creature: hit
   * points and conditions for a linked combatant are owned by the party member,
   * never edited on the row alone.
   */
  char_id?: string;
  name: string;
  initiative: number;
  hp: number;
  max_hp: number;
  ac: number;
  dex: number;
  is_player: boolean;
  portrait?: string;
  statblock?: string;
  conditions: CombatantCondition[];
  /** Only ever set for a player at 0 HP; cleared the moment they are healed. */
  deathSaves?: DeathSaves;
}

/**
 * Everything about a fight in progress that has to outlive a page load. Stored
 * per campaign, so switching workspaces resumes each table where it stood.
 */
export interface EncounterState {
  /** 0 = combat has not started; the first turn is round 1. */
  round: number;
  activeCombatantId: string | null;
  combatants: InitiativeCombatant[];
}
