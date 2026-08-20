import { environment } from '../../../environments/environment';
import type { RollMode } from '../services/dice.service';

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

/**
 * `pending` → the player has been asked and has not answered yet.
 * `resolved` → they rolled. `missed` → they let the prompt lapse.
 * `cancelled` → the DM superseded it with a newer request for the same hero.
 */
export type RollRequestStatus = 'pending' | 'resolved' | 'missed' | 'cancelled';

export interface RollRequestResult {
  total: number;
  expression: string;
  raw: number;
  rolls: number[];
  modifier: number;
  /** How the player chose to throw it. Absent on results rolled before #26. */
  mode?: RollMode;
  /** The part of `modifier` the player added by hand, not read off the sheet. */
  situational_bonus?: number;
}

export interface RollRequest {
  id?: string;
  char_filename: string;
  char_name: string;
  roll_type: string;
  stat: string;
  reason?: string;
  status?: RollRequestStatus;
  result?: RollRequestResult | null;
  /**
   * A secret roll is thrown server-side against the hero's sheet and never reaches
   * them — not over the socket, and not in their replayed history either.
   */
  is_secret?: boolean;
  /** `dm` on a secret roll; absent or `player` when the hero rolled it themselves. */
  rolled_by?: 'dm' | 'player';
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
