export interface SessionOutline {
  session_number: number;
  main_event: string;
  required_npcs: string[];
  location: string;
  plot_hooks: string[];
}

export interface CampaignSkeleton {
  id?: string;
  campaign_name: string;
  concept: string;
  tone: string;
  max_sessions: number;
  plot_twists: string[];
  key_milestones: string[];
  generated_outlines: SessionOutline[];
  created_at?: string;
  updated_at?: string;
}
