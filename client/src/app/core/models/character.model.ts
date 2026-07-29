export interface StatBlock {
  STR: number;
  DEX: number;
  CON: number;
  INT: number;
  WIS: number;
  CHA: number;
}

export interface Weapon {
  name: string;
  attack_bonus: string;
  damage_dice?: string;
  damage_bonus?: string;
  range?: string;
  properties?: string;
  is_custom?: boolean;
  magic_bonus?: number;
  ability_modifier?: string;
  damage?: string;
}

export interface EquipmentItem {
  name: string;
  equipped?: boolean;
  attuned?: boolean;
  ac_bonus?: number;
  mod1?: string;
  val1?: number;
  mod2?: string;
  val2?: number;
}

export interface FeatureTrait {
  name: string;
  description: string;
  source?: string;
}

export interface Advancement {
  level: number;
  type: string;
  name: string;
  description: string;
}

export interface SpellList {
  cantrips?: string[];
  level_1?: string[];
  level_2?: string[];
  level_3?: string[];
  level_4?: string[];
  level_5?: string[];
  level_6?: string[];
  level_7?: string[];
  level_8?: string[];
  level_9?: string[];
}

export interface CharacterSchema {
  char_id?: string;
  owner_id?: string;
  char_name: string;
  is_npc?: boolean;
  gender?: string;
  char_class: string;
  subclass?: string;
  char_level: number;
  race: string;
  background: string;
  alignment?: string;
  backstory?: string;
  armor_class: number;
  hp_max: number;
  hp_current?: number;
  hit_dice_used?: number;
  speed: number;
  proficiency_bonus: number;
  stats: StatBlock;
  saving_throws?: string[];
  skills?: Record<string, number>;
  skill_proficiencies?: string[];
  skill_expertise?: string[];
  weapon_masteries?: string[];
  weapons?: Weapon[];
  equipment?: EquipmentItem[];
  features_traits?: FeatureTrait[];
  spells?: SpellList;
  prepared_spells?: string[];
  spell_slots?: Record<string, { max: number; used: number }>;
  concentrating_on?: string;
  conditions?: string[];
  spell_ability?: string;
  spell_save_dc?: number;
  spell_attack_bonus?: string;
  hit_dice?: string;
  passive_perception?: number;
  saving_throw_values?: Record<string, number>;
  initiative_modifier?: number;
  advancements?: Advancement[];
  personality_traits?: string;
  ideals?: string;
  bonds?: string;
  flaws?: string;
  languages?: string[];
  tool_proficiencies?: string[];
  char_portrait?: string;
  playstyle_guide?: string;
  dnd_edition?: string;
  active_campaign?: string;
}
