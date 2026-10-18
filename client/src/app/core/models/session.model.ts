import { CampaignEntity } from './campaign-entity.model';

export interface SessionLog {
  id?: string;
  campaign_name: string;
  session_number: number;
  title: string;
  session_type?: string;
  summary: string;
  real_world_date?: string;
  extracted_entities?: CampaignEntity[];
  audio_file_id?: string;
  created_at?: string;
}

export interface SessionPrep {
  strong_start: string;
  secrets_clues: string[];
  encounters: string[];
  key_npcs: string[];
}

export interface JourneyNode {
  location_name: string;
  description: string;
  session_number: number;
}

export interface JourneyGraph {
  nodes: JourneyNode[];
}
