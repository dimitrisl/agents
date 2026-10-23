export interface VTTToken {
  id: string;
  name: string;
  image_url?: string;
  x: number;
  y: number;
  size: number;
  is_enemy: boolean;
  hp?: number;
  max_hp?: number;
  is_hidden: boolean;
}

export interface VTTGrid {
  width: number;
  height: number;
  background_image_url?: string;
  cell_size: number;
}

export interface VTTFog {
  enabled: boolean;
  revealed: number[];
}

export interface VTTScene {
  scene_id: string;
  campaign_name: string;
  name: string;
  dm_notes: string;
  grid: VTTGrid;
  tokens: VTTToken[];
  fog: VTTFog;
  order: number;
  is_active_scene: boolean;
  created_at?: string;
  updated_at?: string;
  last_activated_at?: string;
}

export interface VTTState {
  is_active: boolean;
  active_scene_id?: string;
  scene_name?: string;
  grid: VTTGrid;
  tokens: VTTToken[];
  fog?: VTTFog;
}
