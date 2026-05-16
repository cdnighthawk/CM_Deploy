import * as FileSystem from 'expo-file-system/legacy';
import * as SQLite from 'expo-sqlite';

import { downloadWithAuth } from '@/src/api/client';
import type { DrawingSheet } from '@/src/api/drawings';

const DB_NAME = 'usis_cm.db';
const CACHE_CAP_BYTES = 1024 * 1024 * 1024; // 1 GB per project

export type CacheRow = {
  project_id: string;
  drawing_set: string;
  sheet_series_id: string;
  drawing_id: string;
  revision: string | null;
  remote_url: string;
  local_path: string | null;
  bytes: number | null;
  remote_updated_at: string | null;
  downloaded_at: string | null;
  status: 'pending' | 'complete' | 'failed';
};

let dbPromise: Promise<SQLite.SQLiteDatabase> | null = null;

async function getDb(): Promise<SQLite.SQLiteDatabase> {
  if (!dbPromise) {
    dbPromise = SQLite.openDatabaseAsync(DB_NAME);
  }
  return dbPromise;
}

export async function initDrawingCacheDb(): Promise<void> {
  const db = await getDb();
  await db.execAsync(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS cached_drawings (
      project_id TEXT NOT NULL,
      drawing_set TEXT NOT NULL,
      sheet_series_id TEXT NOT NULL,
      drawing_id TEXT NOT NULL,
      revision TEXT,
      remote_url TEXT NOT NULL,
      local_path TEXT,
      bytes INTEGER,
      remote_updated_at TEXT,
      downloaded_at TEXT,
      status TEXT NOT NULL DEFAULT 'pending',
      PRIMARY KEY (project_id, drawing_set, sheet_series_id)
    );
    CREATE TABLE IF NOT EXISTS user_preferences (
      key TEXT PRIMARY KEY NOT NULL,
      value TEXT NOT NULL
    );
  `);
}

function setSlug(name: string): string {
  return name.replace(/[^a-zA-Z0-9._-]+/g, '_').slice(0, 80) || 'default';
}

function cacheDir(projectId: string, drawingSet: string): string {
  const root = FileSystem.documentDirectory ?? '';
  return `${root}drawings/${projectId}/${setSlug(drawingSet)}/`;
}

export async function getPreference(key: string): Promise<string | null> {
  await initDrawingCacheDb();
  const db = await getDb();
  const row = await db.getFirstAsync<{ value: string }>(
    'SELECT value FROM user_preferences WHERE key = ?',
    [key],
  );
  return row?.value ?? null;
}

export async function setPreference(key: string, value: string): Promise<void> {
  await initDrawingCacheDb();
  const db = await getDb();
  await db.runAsync(
    'INSERT INTO user_preferences (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value',
    [key, value],
  );
}

export function prefKeyDrawingSet(projectId: string): string {
  return `drawing_set:${projectId}`;
}

export async function listCachedRows(
  projectId: string,
  drawingSet: string,
): Promise<CacheRow[]> {
  await initDrawingCacheDb();
  const db = await getDb();
  return db.getAllAsync<CacheRow>(
    `SELECT * FROM cached_drawings WHERE project_id = ? AND drawing_set = ? ORDER BY sheet_series_id`,
    [projectId, drawingSet],
  );
}

export async function upsertPendingRows(
  projectId: string,
  drawingSet: string,
  sheets: DrawingSheet[],
): Promise<void> {
  await initDrawingCacheDb();
  const db = await getDb();
  for (const sheet of sheets) {
    const rev = sheet.current_revision;
    const url = rev?.file_url;
    if (!url || !rev?.id) continue;
    await db.runAsync(
      `INSERT INTO cached_drawings (
        project_id, drawing_set, sheet_series_id, drawing_id, revision,
        remote_url, remote_updated_at, status
      ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
      ON CONFLICT(project_id, drawing_set, sheet_series_id) DO UPDATE SET
        drawing_id = excluded.drawing_id,
        revision = excluded.revision,
        remote_url = excluded.remote_url,
        remote_updated_at = excluded.remote_updated_at,
        status = CASE
          WHEN cached_drawings.remote_updated_at IS NOT excluded.remote_updated_at
            OR cached_drawings.status = 'failed' THEN 'pending'
          ELSE cached_drawings.status
        END`,
      [
        projectId,
        drawingSet,
        sheet.series_id,
        rev.id,
        rev.revision,
        url,
        rev.updated_at,
      ],
    );
  }
}

export type DownloadProgress = {
  done: number;
  total: number;
  currentSheet?: string;
};

export async function downloadDrawingSet(
  projectId: string,
  drawingSet: string,
  onProgress?: (p: DownloadProgress) => void,
): Promise<void> {
  await initDrawingCacheDb();
  const dir = cacheDir(projectId, drawingSet);
  await FileSystem.makeDirectoryAsync(dir, { intermediates: true });

  const rows = await listCachedRows(projectId, drawingSet);
  const pending = rows.filter((r) => r.status !== 'complete' || !r.local_path);
  const total = pending.length || rows.length;
  let done = 0;

  for (const row of pending.length ? pending : rows) {
    if (!row.remote_url) continue;
    onProgress?.({
      done,
      total,
      currentSheet: row.sheet_series_id,
    });
    const localPath = `${dir}${row.drawing_id}.pdf`;
    const db = await getDb();
    try {
      await downloadWithAuth(row.remote_url, localPath);
      const info = await FileSystem.getInfoAsync(localPath);
      const bytes = info.exists && 'size' in info ? (info.size as number) : null;
      await db.runAsync(
        `UPDATE cached_drawings SET local_path = ?, bytes = ?, downloaded_at = ?, status = 'complete'
         WHERE project_id = ? AND drawing_set = ? AND sheet_series_id = ?`,
        [
          localPath,
          bytes,
          new Date().toISOString(),
          projectId,
          drawingSet,
          row.sheet_series_id,
        ],
      );
    } catch {
      await db.runAsync(
        `UPDATE cached_drawings SET status = 'failed' WHERE project_id = ? AND drawing_set = ? AND sheet_series_id = ?`,
        [projectId, drawingSet, row.sheet_series_id],
      );
    }
    done += 1;
    onProgress?.({ done, total });
  }

  await enforceCacheCap(projectId);
}

async function enforceCacheCap(projectId: string): Promise<void> {
  const base = `${FileSystem.documentDirectory ?? ''}drawings/${projectId}/`;
  const info = await FileSystem.getInfoAsync(base);
  if (!info.exists) return;

  const db = await getDb();
  const rows = await db.getAllAsync<{ bytes: number | null; drawing_set: string }>(
    `SELECT bytes, drawing_set FROM cached_drawings WHERE project_id = ? AND status = 'complete'`,
    [projectId],
  );
  let total = rows.reduce((n, r) => n + (r.bytes ?? 0), 0);
  if (total <= CACHE_CAP_BYTES) return;

  const sets = [...new Set(rows.map((r) => r.drawing_set))];
  for (const setName of sets) {
    if (total <= CACHE_CAP_BYTES) break;
    await clearDrawingSetCache(projectId, setName);
    total = 0;
  }
}

export async function clearDrawingSetCache(
  projectId: string,
  drawingSet: string,
): Promise<void> {
  const dir = cacheDir(projectId, drawingSet);
  await FileSystem.deleteAsync(dir, { idempotent: true });
  const db = await getDb();
  await db.runAsync(
    'DELETE FROM cached_drawings WHERE project_id = ? AND drawing_set = ?',
    [projectId, drawingSet],
  );
}

export async function cacheSummary(
  projectId: string,
  drawingSet: string,
): Promise<{ complete: number; total: number; bytes: number }> {
  const rows = await listCachedRows(projectId, drawingSet);
  const complete = rows.filter((r) => r.status === 'complete' && r.local_path);
  const bytes = complete.reduce((n, r) => n + (r.bytes ?? 0), 0);
  return { complete: complete.length, total: rows.length, bytes };
}
