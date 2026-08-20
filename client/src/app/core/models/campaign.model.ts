import { environment } from '../../../environments/environment';

/**
 * Builds an API URL for one campaign. The campaign name is the primary key and
 * it is DM-authored prose — spaces, `&`, and above all `#`, which truncates the
 * rest of the URL and silently retargets the request at a different endpoint.
 * Every caller goes through here so the encoding cannot drift call by call.
 *
 * `path` is appended as-is: it is a literal route suffix or a server-generated
 * id, never user input.
 *
 * Known gap: a name containing `/` still 404s. Percent-encoding does not save
 * it, because the ASGI server decodes `%2F` before the route is matched and the
 * path gains a segment. That one needs campaign_id (#13).
 */
export function campaignUrl(campaignName: string, path = ''): string {
  const base = `${environment.apiBaseUrl}/campaigns/${encodeURIComponent(campaignName)}`;
  return path ? `${base}/${path}` : base;
}

export interface RollRequest {
  id?: string;
  char_filename: string;
  char_name: string;
  roll_type: string;
  stat: string;
  reason?: string;
  status?: string;
  result?: {
    total: number;
    expression: string;
    raw: number;
    rolls: number[];
    modifier: number;
  } | null;
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

/** Replayed history for one campaign channel — `GET /campaigns/{name}/messages`. */
export interface CampaignMessages {
  campaign_name: string;
  whispers: Whisper[];
  roll_requests: RollRequest[];
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
