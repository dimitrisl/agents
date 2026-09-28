export interface CampaignEntity {
  id?: string;
  campaign_name: string;
  name: string;
  type: string; // 'npc' | 'villain' | 'faction' | 'location' | 'lore' | 'monster'
  content: string; // Markdown
  tags: string[];
  stats?: Record<string, any>;
  created_at?: string;
}

export interface PasteExtractionRequest {
  raw_text: string;
}
