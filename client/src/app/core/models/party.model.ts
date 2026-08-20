/**
 * A hero as the DM's workspace tracks them: the roster row behind the party
 * tab, the initiative row, the whisper recipient and the roll target.
 *
 * Hit points and conditions live here and nowhere else. An `InitiativeCombatant`
 * for the same hero is a view of this record, never a second copy — see the
 * "one hero, one state" section of `dm.component.ts`.
 */
export interface PartyMember {
  /** Absent for a member the DM typed in by hand: there is no sheet to write to. */
  char_id?: string;
  name: string;
  char_class: string;
  level: number;
  hp_current: number;
  hp_max: number;
  ac: number;
  passive_perception: number;
  conditions: string[];
  stats?: { [key: string]: number };
  portrait?: string;
}

/**
 * Passive Perception from the hero's own Wisdom, for every path that builds a
 * `PartyMember`. It was inlined three times, and one of those spellings had the
 * ability score hardcoded — the number on screen was 11 for everyone, whatever
 * the sheet said.
 */
export function passivePerception(stats?: { [key: string]: number }): number {
  const wisdom = stats?.['WIS'] ?? 10;
  return 10 + Math.floor((wisdom - 10) / 2);
}
