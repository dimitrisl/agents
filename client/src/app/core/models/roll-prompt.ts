import type { RollRequest } from './campaign.model';

/**
 * How long the player has to answer before a request is reported back as missed.
 *
 * Long enough to read the reason and think, short enough that the DM is not left
 * staring at "waiting" for a player who walked away from the table.
 */
export const ROLL_PROMPT_TIMEOUT_SECONDS = 60;

/** What the prompt queue already knows about, so nothing is asked twice. */
export interface RollPromptState {
  /** Requests this session has already answered — the socket echoes them back. */
  answeredIds: ReadonlySet<string>;
  queued: readonly RollRequest[];
  active: RollRequest | null;
}

/** A request still wants an answer only while the DM has not moved on from it. */
export function isAwaitingPlayer(request: RollRequest): boolean {
  return (request.status || 'pending') === 'pending';
}

/**
 * The single gate every prompt goes through, from the socket and from catch-up
 * alike. Catch-up replays the whole thread on every reconnect, so without this a
 * flaky connection would ask the player the same question once per drop.
 */
export function shouldPrompt(request: RollRequest, state: RollPromptState): boolean {
  if (!isAwaitingPlayer(request)) return false;

  const id = request.id;
  if (!id) return true;

  if (state.answeredIds.has(id)) return false;
  if (state.active?.id === id) return false;
  return !state.queued.some((queued) => queued.id === id);
}

/**
 * The DM supersedes a pending request by sending a new one for the same hero, which
 * cancels the old one server-side. A prompt already waiting in the queue for that
 * cancelled request is a question about a moment that has passed — drop it.
 */
export function dropStalePrompts(
  queued: readonly RollRequest[],
  request: RollRequest
): RollRequest[] {
  if (isAwaitingPlayer(request)) return [...queued];
  return queued.filter((entry) => entry.id !== request.id);
}
