export interface RollRequest {
  id?: string;
  char_filename: string;
  char_name: string;
  roll_type: string;
  stat: string;
  reason?: string;
  status?: string;
  result?: string;
  is_secret?: boolean;
  created_at?: string;
}

export interface Whisper {
  id?: string;
  sender: string;
  recipient: string;
  message: string;
  timestamp?: string;
}

export interface Campaign {
  campaign_name: string;
  owner_id?: string;
  notes?: string;
  party: string[];
  dnd_edition?: string;
  invite_code?: string;
  roll_requests?: RollRequest[];
  whispers?: Whisper[];
}
