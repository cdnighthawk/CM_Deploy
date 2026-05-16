import * as Network from 'expo-network';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  View,
} from 'react-native';

import { ApiError } from '@/src/api/client';
import {
  defaultDrawingSet,
  distinctDrawingSets,
  fetchProjectDrawings,
  filterSheetsBySet,
  type DrawingSheet,
} from '@/src/api/drawings';
import {
  cacheSummary,
  downloadDrawingSet,
  getPreference,
  listCachedRows,
  prefKeyDrawingSet,
  setPreference,
  upsertPendingRows,
  type CacheRow,
  type DownloadProgress,
} from '@/src/drawings/cache';

const WIFI_ONLY_KEY = 'wifi_only_downloads';

export default function ProjectDrawingsScreen() {
  const { id: projectId } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [sheets, setSheets] = useState<DrawingSheet[]>([]);
  const [sets, setSets] = useState<string[]>([]);
  const [activeSet, setActiveSet] = useState<string>('');
  const [cached, setCached] = useState<CacheRow[]>([]);
  const [summary, setSummary] = useState({ complete: 0, total: 0, bytes: 0 });
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState<DownloadProgress | null>(null);
  const [wifiOnly, setWifiOnly] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshCache = useCallback(async () => {
    if (!projectId || !activeSet) return;
    const rows = await listCachedRows(projectId, activeSet);
    setCached(rows);
    setSummary(await cacheSummary(projectId, activeSet));
  }, [projectId, activeSet]);

  const loadDrawings = useCallback(async () => {
    if (!projectId) return;
    setError(null);
    try {
      const all = await fetchProjectDrawings(projectId);
      setSheets(all);
      const setNames = distinctDrawingSets(all);
      setSets(setNames);
      const saved = await getPreference(prefKeyDrawingSet(projectId));
      const initial =
        saved && setNames.includes(saved) ? saved : defaultDrawingSet(all);
      setActiveSet(initial);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load drawings');
    }
  }, [projectId]);

  useEffect(() => {
    getPreference(WIFI_ONLY_KEY).then((v) => {
      if (v !== null) setWifiOnly(v !== '0');
    });
  }, []);

  useEffect(() => {
    loadDrawings().finally(() => setLoading(false));
  }, [loadDrawings]);

  useEffect(() => {
    refreshCache();
  }, [refreshCache, activeSet]);

  async function selectSet(setName: string) {
    if (!projectId) return;
    setActiveSet(setName);
    await setPreference(prefKeyDrawingSet(projectId), setName);
    const filtered = filterSheetsBySet(sheets, setName);
    await upsertPendingRows(projectId, setName, filtered);
    await refreshCache();
  }

  async function onDownload() {
    if (!projectId || !activeSet) return;
    const net = await Network.getNetworkStateAsync();
    if (wifiOnly && net.type !== Network.NetworkStateType.WIFI) {
      Alert.alert(
        'Wi‑Fi only',
        'Downloads on cellular are disabled. Connect to Wi‑Fi or turn off Wi‑Fi only in settings below.',
      );
      return;
    }
    const filtered = filterSheetsBySet(sheets, activeSet);
    await upsertPendingRows(projectId, activeSet, filtered);
    setDownloading(true);
    setProgress({ done: 0, total: filtered.length });
    try {
      await downloadDrawingSet(projectId, activeSet, setProgress);
      await refreshCache();
    } catch (e) {
      Alert.alert('Download failed', e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setDownloading(false);
      setProgress(null);
    }
  }

  function openSheet(row: CacheRow) {
    if (row.status !== 'complete' || !row.local_path) {
      Alert.alert('Not cached', 'Download this drawing set first.');
      return;
    }
    router.push({
      pathname: '/(app)/projects/[id]/viewer',
      params: {
        id: projectId!,
        localPath: row.local_path,
        title: row.sheet_series_id,
      },
    });
  }

  const displaySheets = cached.length
    ? cached
    : filterSheetsBySet(sheets, activeSet).map((s) => ({
        project_id: projectId!,
        drawing_set: activeSet,
        sheet_series_id: s.sheet_number || s.series_id,
        drawing_id: s.current_revision.id,
        revision: s.current_revision.revision,
        remote_url: s.current_revision.file_url || '',
        local_path: null,
        bytes: null,
        remote_updated_at: s.current_revision.updated_at,
        downloaded_at: null,
        status: 'pending' as const,
      }));

  return (
    <View style={styles.root}>
      <Stack.Screen options={{ title: 'Drawings' }} />
      {loading ? (
        <ActivityIndicator style={{ marginTop: 24 }} />
      ) : error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <>
          <Text style={styles.label}>Drawing set</Text>
          <View style={styles.setRow}>
            {sets.map((s) => (
              <Pressable
                key={s}
                style={[styles.chip, s === activeSet && styles.chipActive]}
                onPress={() => selectSet(s)}
              >
                <Text style={[styles.chipText, s === activeSet && styles.chipTextActive]}>
                  {s}
                </Text>
              </Pressable>
            ))}
          </View>

          <Text style={styles.summary}>
            Cached {summary.complete}/{summary.total} sheets ·{' '}
            {(summary.bytes / (1024 * 1024)).toFixed(1)} MB
          </Text>

          <View style={styles.wifiRow}>
            <Text style={styles.wifiLabel}>Wi‑Fi only downloads</Text>
            <Switch
              value={wifiOnly}
              onValueChange={async (v) => {
                setWifiOnly(v);
                await setPreference(WIFI_ONLY_KEY, v ? '1' : '0');
              }}
            />
          </View>

          <Pressable
            style={[styles.downloadBtn, downloading && styles.downloadBtnDisabled]}
            onPress={onDownload}
            disabled={downloading}
          >
            {downloading ? (
              <Text style={styles.downloadBtnText}>
                Downloading {progress?.done ?? 0}/{progress?.total ?? 0}…
              </Text>
            ) : (
              <Text style={styles.downloadBtnText}>Download set</Text>
            )}
          </Pressable>

          <FlatList
            data={displaySheets}
            keyExtractor={(item) => item.sheet_series_id}
            renderItem={({ item }) => (
              <Pressable style={styles.sheetRow} onPress={() => openSheet(item)}>
                <Text style={styles.sheetTitle}>
                  {item.sheet_series_id}
                  {item.revision ? ` · Rev ${item.revision}` : ''}
                </Text>
                <Text style={styles.sheetStatus}>
                  {item.status === 'complete' ? 'Offline' : item.status}
                </Text>
              </Pressable>
            )}
          />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f8fafc', padding: 12 },
  label: { fontSize: 13, color: '#64748b', marginBottom: 6 },
  setRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    backgroundColor: '#e2e8f0',
  },
  chipActive: { backgroundColor: '#1d4ed8' },
  chipText: { fontSize: 13, color: '#334155' },
  chipTextActive: { color: '#fff' },
  summary: { fontSize: 13, color: '#475569', marginBottom: 8 },
  wifiRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  wifiLabel: { fontSize: 14, color: '#334155' },
  downloadBtn: {
    backgroundColor: '#1d4ed8',
    padding: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  downloadBtnDisabled: { opacity: 0.7 },
  downloadBtnText: { color: '#fff', fontWeight: '600' },
  sheetRow: {
    backgroundColor: '#fff',
    padding: 14,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
  },
  sheetTitle: { fontSize: 15, fontWeight: '500', color: '#0f172a' },
  sheetStatus: { fontSize: 12, color: '#64748b', marginTop: 4 },
  error: { color: '#b91c1c', padding: 16 },
});
