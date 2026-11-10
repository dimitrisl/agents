/**
 * 6 core ability scores for monsters, bounded between 1 and 30.
 */
export interface MonsterStats {
  str: number;
  dex: number;
  con: number;
  int: number;
  wis: number;
  cha: number;
}

/**
 * Special trait or passive feature of a monster.
 */
export interface MonsterTrait {
  name: string;
  description?: string;
  /** Fallback description field supported for SRD tolerance. */
  desc?: string;
}

/**
 * Structured attack or active action of a monster.
 */
export interface MonsterAction {
  name: string;
  attack_bonus?: number | null;
  damage_dice?: string | null;
  damage_type?: string | null;
  description?: string;
  /** Fallback description field supported for SRD tolerance. */
  desc?: string;
}

/**
 * Complete unified Bestiary monster representation.
 */
export interface BestiaryMonster {
  id: string;
  name: string;
  edition: string; // '2014' | '2024'
  origin: 'official' | 'custom' | 'community';
  is_public: boolean;
  creator_dm_id?: string | null;
  based_on?: string | null;
  size: string; // 'Tiny' | 'Small' | 'Medium' | 'Large' | 'Huge' | 'Gargantuan'
  type: string; // 'humanoid', 'beast', 'dragon', etc.
  subtype?: string | null;
  alignment: string;
  cr: string;
  cr_numeric: number;
  ac: number;
  hp: number;
  max_hp: number;
  speed: string;
  stats: MonsterStats;
  senses?: string | null;
  languages?: string | null;
  description?: string | null;
  traits: MonsterTrait[];
  actions: MonsterAction[];
  bonus_actions?: MonsterAction[];
  reactions?: MonsterAction[];
  legendary_actions?: MonsterAction[];
  condition_immunities?: string[];
  damage_immunities?: string[];
  damage_resistances?: string[];
  xp?: number;
  created_at?: string;
  updated_at?: string;
}

export type Monster = BestiaryMonster;

/**
 * Request payload for creating a custom monster or cloning via based_on.
 */
export interface BestiaryCreateRequest {
  name: string;
  edition?: string;
  size?: string;
  type?: string;
  subtype?: string | null;
  alignment?: string;
  cr?: string;
  cr_numeric?: number;
  ac?: number;
  hp?: number;
  max_hp?: number;
  speed?: string;
  stats?: MonsterStats;
  senses?: string | null;
  languages?: string | null;
  description?: string | null;
  traits?: MonsterTrait[];
  actions?: MonsterAction[];
  bonus_actions?: MonsterAction[];
  reactions?: MonsterAction[];
  legendary_actions?: MonsterAction[];
  condition_immunities?: string[];
  damage_immunities?: string[];
  damage_resistances?: string[];
  is_public?: boolean;
  based_on?: string;
}

/**
 * Request payload for updating an existing custom monster (partial updates supported).
 */
export interface BestiaryUpdateRequest {
  name?: string;
  edition?: string;
  size?: string;
  type?: string;
  subtype?: string | null;
  alignment?: string;
  cr?: string;
  cr_numeric?: number;
  ac?: number;
  hp?: number;
  max_hp?: number;
  speed?: string;
  stats?: MonsterStats;
  senses?: string | null;
  languages?: string | null;
  description?: string | null;
  traits?: MonsterTrait[];
  actions?: MonsterAction[];
  bonus_actions?: MonsterAction[];
  reactions?: MonsterAction[];
  legendary_actions?: MonsterAction[];
  condition_immunities?: string[];
  damage_immunities?: string[];
  damage_resistances?: string[];
  is_public?: boolean;
}

/**
 * Request payload for toggling custom monster public visibility.
 */
export interface BestiaryVisibilityRequest {
  is_public: boolean;
}

/**
 * Response contract for visibility toggle.
 */
export interface BestiaryVisibilityResponse {
  success: boolean;
  is_public: boolean;
}

/**
 * Response contract for monster deletion.
 */
export interface BestiaryDeleteResponse {
  success: boolean;
  message: string;
}

/**
 * Query filter parameters for searching and listing Bestiary monsters.
 */
export interface BestiaryFilterParams {
  edition?: string;
  search?: string;
  cr?: string;
  cr_min?: number;
  cr_max?: number;
  monster_type?: string;
  include_official?: boolean;
  include_mine?: boolean;
  include_community?: boolean;
}
