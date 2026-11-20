import { ClassResource } from '../models/character.model';

export interface ClassResourceDraft {
  name: string;
  max: number;
  recharge: 'short' | 'long';
  current: number;
  bonus: number;
}

/** What the class rules alone give an auto-tracked resource pool. */
export function resourceRulesMax(res: ClassResource | null | undefined): number {
  return res ? res.max - (res.bonus ?? 0) : 0;
}

/** Computes the clamped maximum charges for an edited or new resource pool. */
export function resourceEditedMax(
  editing: ClassResource | null | undefined,
  newMax: number,
  newBonus: number
): number {
  if (editing?.auto) {
    return Math.max(1, resourceRulesMax(editing) + (Number(newBonus) || 0));
  }
  return Math.max(1, Number(newMax) || 1);
}

/** Immutably inserts or updates a class resource pool. Returns `null` if a new custom name is blank. */
export function upsertClassResourceList(
  resources: ClassResource[] | undefined,
  editing: ClassResource | null,
  draft: ClassResourceDraft
): ClassResource[] | null {
  const existing = resources ?? [];
  if (editing) {
    const max = resourceEditedMax(editing, draft.max, draft.bonus);
    const current = Math.min(max, Math.max(0, Math.floor(Number(draft.current) || 0)));
    const rulesMax = resourceRulesMax(editing);
    const changes: Partial<ClassResource> = editing.auto
      ? { max, current, bonus: max - rulesMax }
      : {
          name: draft.name.trim() || editing.name,
          max,
          current,
          recharge: draft.recharge,
        };
    return existing.map((r) => (r === editing ? { ...r, ...changes } : r));
  }

  const cleanName = draft.name.trim();
  if (!cleanName) return null;

  const maxVal = Math.max(1, Math.floor(Number(draft.max) || 1));
  return [
    ...existing,
    {
      name: cleanName,
      current: maxVal,
      max: maxVal,
      recharge: draft.recharge,
    },
  ];
}

/** Immutably updates `current` on a single pool clamped to `[0, res.max]`. */
export function setClassResourceCurrent(
  resources: ClassResource[] | undefined,
  target: ClassResource,
  nextCurrent: number
): ClassResource[] {
  return (resources ?? []).map((r) =>
    r === target
      ? { ...r, current: Math.max(0, Math.min(r.max, Math.floor(nextCurrent))) }
      : r
  );
}

/** Immutably deletes the pool at `index`. */
export function removeClassResourceAt(
  resources: ClassResource[] | undefined,
  index: number
): ClassResource[] {
  return (resources ?? []).filter((_, i) => i !== index);
}
