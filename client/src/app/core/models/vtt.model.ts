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

export interface VTTState {
  is_active: boolean;
  grid: VTTGrid;
  tokens: VTTToken[];
}
