import { RollRequest, Whisper } from './campaign.model';

/**
 * One entry in the campaign thread. Whispers and roll requests share a single
 * chronological feed — the timestamp is what tells them apart, not a section.
 */
export type InboxEntry =
  | { kind: 'whisper'; key: string; at: number; whisper: Whisper }
  | { kind: 'roll'; key: string; at: number; request: RollRequest };

/**
 * Mongo stores a naive UTC string ("2026-08-02 19:04:11"); the trailing Z is
 * what makes it read as local time instead of drifting by the offset.
 */
export function inboxTime(timestamp?: string): number {
  if (!timestamp) return 0;
  const normalized = timestamp.includes('T') ? timestamp : `${timestamp.replace(' ', 'T')}Z`;
  const value = new Date(normalized).getTime();
  return Number.isNaN(value) ? 0 : value;
}

export function formatInboxTime(timestamp?: string): string {
  if (!timestamp) return 'Just now';

  const value = inboxTime(timestamp);
  if (!value) return timestamp;

  return new Intl.DateTimeFormat('el-GR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

/** Interleaves both message kinds into one thread, oldest first. */
export function buildInboxFeed(whispers: Whisper[], rollRequests: RollRequest[]): InboxEntry[] {
  const entries: InboxEntry[] = [
    ...whispers.map((whisper, index) => ({
      kind: 'whisper' as const,
      key: whisper.id || `w-${whisper.timestamp || 'no-time'}-${index}`,
      at: inboxTime(whisper.timestamp),
      whisper,
    })),
    ...rollRequests.map((request, index) => ({
      kind: 'roll' as const,
      key: request.id || `r-${request.created_at || 'no-time'}-${index}`,
      at: inboxTime(request.created_at),
      request,
    })),
  ];

  return entries.sort((a, b) => a.at - b.at);
}
