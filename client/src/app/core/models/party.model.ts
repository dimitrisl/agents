/**
 * A hero as the DM's workspace tracks them: the roster row behind the party
 * tab, the initiative row, the whisper recipient and the roll target.
 *
 * Hit points and conditions live here and nowhere else. An `InitiativeCombatant`
 * for the same hero is a view of this record, never a second copy — see the
 * "one hero, one state" section of `dm.component.ts`.
 */
import type { AcBreakdown, ClassEntry, DmModifiers, FeatureTrait } from './character.model';

export interface PartyMember {
  /** Absent for a member the DM typed in by hand: there is no sheet to write to. */
  char_id?: string;
  name: string;
  char_class: string;
  level: number;
  race?: string;
  classes?: ClassEntry[];
  dnd_edition?: string;
  ruleset_version?: string;
  hp_current: number;
  hp_max: number;
  hp_temp?: number;
  ac: number;
  ac_breakdown?: AcBreakdown;
  speed?: number;
  passive_perception: number;
  conditions: string[];
  senses?: string[];
  features_traits?: FeatureTrait[];
  damage_resistances?: string[];
  damage_immunities?: string[];
  damage_vulnerabilities?: string[];
  save_advantages?: string[];
  concentrating_on?: string | null;
  death_saves?: { successes: number; failures: number };
  inspiration?: boolean;
  exhaustion_level?: number;
  exhaustion_bypass?: boolean;
  magic_items_suppressed?: boolean;
  dm_modifiers?: DmModifiers;
  dm_short_rest_unlocked?: boolean;
  dm_long_rest_unlocked?: boolean;
  dm_level_up_unlocked?: boolean;
  initiative_modifier?: number;
  initiative_advantage?: boolean;
  stats?: { [key: string]: number };
  portrait?: string;
  owner_username?: string;
  isOnline?: boolean;
}

/**
 * Passive Perception from the hero's own Wisdom, for every path that builds a
 * `PartyMember`. It was inlined three times, and one of those spellings had the
 * ability score hardcoded — the number on screen was 11 for everyone, whatever
 * the sheet said.
 */
