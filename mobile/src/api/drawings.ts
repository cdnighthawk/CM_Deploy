import { apiFetch } from '@/src/api/client';

export type DrawingRevision = {
  id: string;
  revision: string | null;
  file_url: string | null;
  updated_at: string | null;
  sheet_number: string | null;
  sheet_title: string | null;
};

export type DrawingSheet = {
  series_id: string;
  sheet_number: string | null;
  sheet_title: string | null;
  discipline: string | null;
  drawing_set: string | null;
  current_revision: DrawingRevision;
};

type DrawingsListResponse = {
  items: DrawingSheet[];
  total: number;
};

export async function fetchProjectDrawings(
  projectId: string,
  drawingSet?: string,
): Promise<DrawingSheet[]> {
  const qs = drawingSet
    ? `?drawing_set=${encodeURIComponent(drawingSet)}`
    : '';
  const data = await apiFetch<DrawingsListResponse>(
    `/api/v1/projects/${projectId}/drawings${qs}`,
  );
  return data.items ?? [];
}

export function distinctDrawingSets(sheets: DrawingSheet[]): string[] {
  const sets = new Set<string>();
  for (const s of sheets) {
    const name = (s.drawing_set || '').trim() || '(no set)';
    sets.add(name);
  }
  return Array.from(sets).sort();
}

export function defaultDrawingSet(sheets: DrawingSheet[]): string {
  const sets = distinctDrawingSets(sheets);
  if (!sets.length) return '(no set)';
  let best = sets[0];
  let bestTs = '';
  for (const setName of sets) {
    const inSet = sheets.filter(
      (s) => ((s.drawing_set || '').trim() || '(no set)') === setName,
    );
    const maxUpdated = inSet
      .map((s) => s.current_revision?.updated_at || '')
      .sort()
      .pop();
    if (maxUpdated && maxUpdated > bestTs) {
      bestTs = maxUpdated;
      best = setName;
    }
  }
  return best;
}

export function filterSheetsBySet(sheets: DrawingSheet[], setName: string): DrawingSheet[] {
  return sheets.filter(
    (s) => ((s.drawing_set || '').trim() || '(no set)') === setName,
  );
}
