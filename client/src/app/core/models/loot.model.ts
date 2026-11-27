export interface OfficialLootItem {
  name: string;
  type?: string;
  rarity?: string;
  weight?: number | string | null;
  cost_gp?: number | null;
  ac_base?: number | null;
  ac_bonus?: number | null;
  magic_bonus?: number | null;
  requires_attunement?: boolean;
  description?: string | null;
}

export type LootCoinKey = 'pp' | 'gp' | 'ep' | 'sp' | 'cp';
export type LootItemSource = 'custom' | 'official' | 'homebrew';
