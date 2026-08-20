import { CharacterSchema, FeatureTrait } from '../models/character.model';

/** The slice of the server's level-up analysis that the sheet writes back. */
export interface LevelUpAnalysis {
  new_total_hp: number;
  new_features?: FeatureTrait[];
}

export interface LevelUpResult {
  char_level: number;
  hp_max: number;
  /** Levelling up heals to full — what the sheet has always done. */
  hp_current: number;
  /**
   * Left `undefined` when the analysis brought no features, so the caller knows
   * to leave the existing list untouched rather than overwrite it with `[]`.
   */
  features_traits?: FeatureTrait[];
}

/**
 * What a level-up writes onto the sheet.
 *
 * Note what is *not* here: `proficiency_bonus`. The sheet has never recalculated
 * it on level up, so a hero crossing level 5 keeps a stale `+2` on every
 * proficient skill and save. That is a real rules bug and it is tracked
 * separately — this function pins today's behaviour, it does not fix it.
 */
export function levelUp(char: CharacterSchema, analysis: LevelUpAnalysis): LevelUpResult {
  const result: LevelUpResult = {
    char_level: (char.char_level || 1) + 1,
    hp_max: analysis.new_total_hp,
    hp_current: analysis.new_total_hp,
  };

  if (analysis.new_features) {
    result.features_traits = [...(char.features_traits ?? []), ...analysis.new_features];
  }

  return result;
}
