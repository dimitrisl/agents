export interface StorySceneCard {
  card_id?: string;
  title: string;
  image_url: string;
  caption: string;
  dm_notes: string;
  entity_id?: string | null;
  order?: number;
}

export interface StoryScene {
  scene_id?: string;
  campaign_name?: string;
  title: string;
  dm_notes: string;
  order?: number;
  cards: StorySceneCard[];
  created_at?: string;
  updated_at?: string;
}

export interface StorySceneCreatePayload {
  title: string;
  dm_notes?: string;
  order?: number;
  cards: StorySceneCard[];
}

export interface StorySceneUpdatePayload {
  title?: string;
  dm_notes?: string;
  order?: number;
  cards?: StorySceneCard[];
}

export type StoryTargetMode = 'all' | 'selected';

export interface StorySceneCastRequest {
  card_id: string;
  target_mode: StoryTargetMode;
  target_char_ids?: string[];
}

export interface StorySceneDismissRequest {
  target_mode: StoryTargetMode;
  target_char_ids?: string[];
}

export interface ScenePopupPayload {
  scene_id: string;
  scene_title: string;
  card_id: string;
  title: string;
  image_url: string;
  caption: string;
  target_mode: StoryTargetMode;
  target_char_ids: string[];
  sent_at?: string;
}

export interface ScenePopupDismissPayload {
  target_mode: StoryTargetMode;
  target_char_ids: string[];
}
