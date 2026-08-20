/**
 * Response shapes for the AI DM tools (`/api/v1/dm/*`).
 *
 * These mirror the backend schemas exactly — the key names are the contract.
 * Type every `http.post` against them instead of `post<any>()`: an untyped call
 * is what let `prep_markdown` (a field that never existed) reach production.
 */

/** `POST /dm/encounter` → `EncounterSchema.monsters[]` */
export interface EncounterMonster {
  name: string;
  hp: number;
  ac: number;
  dex: number;
  quantity: number;
  statblock_summary: string;
}

/** `POST /dm/encounter` → `EncounterSchema` */
export interface EncounterResponse {
  encounter_text: string;
  monsters: EncounterMonster[];
}

/** `POST /dm/npc` → `NpcResponse` */
export interface NpcResponse {
  npc_markdown: string;
}

/** `POST /dm/session-prep` → `SessionPrepResponse` */
export interface SessionPrepResponse {
  session_markdown: string;
}
