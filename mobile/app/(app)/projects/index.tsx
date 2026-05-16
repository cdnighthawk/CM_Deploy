import { Stack, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ApiError } from '@/src/api/client';
import { fetchProjects, type ProjectSummary } from '@/src/api/projects';

export default function ProjectsScreen() {
  const router = useRouter();
  const [items, setItems] = useState<ProjectSummary[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const rows = await fetchProjects();
      setItems(rows);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Failed to load projects');
    }
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const filtered = items.filter((p) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    const blob = `${p.number ?? ''} ${p.name} ${p.city ?? ''} ${p.state ?? ''}`.toLowerCase();
    return blob.includes(q);
  });

  return (
    <View style={styles.root}>
      <Stack.Screen options={{ title: 'Projects' }} />
      <TextInput
        style={styles.search}
        placeholder="Search by number or name"
        value={query}
        onChangeText={setQuery}
      />
      {loading ? (
        <ActivityIndicator style={{ marginTop: 32 }} />
      ) : error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => item.id}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={<Text style={styles.empty}>No projects found.</Text>}
          renderItem={({ item }) => (
            <Pressable
              style={styles.row}
              onPress={() => router.push(`/(app)/projects/${item.id}`)}
            >
              <Text style={styles.rowTitle}>
                {item.number ? `${item.number} — ` : ''}
                {item.name}
              </Text>
              <Text style={styles.rowSub}>
                {[item.city, item.state].filter(Boolean).join(', ') || item.status || '—'}
              </Text>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f8fafc' },
  search: {
    margin: 12,
    borderWidth: 1,
    borderColor: '#cbd5e1',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    backgroundColor: '#fff',
  },
  row: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e2e8f0',
    backgroundColor: '#fff',
  },
  rowTitle: { fontSize: 16, fontWeight: '600', color: '#0f172a' },
  rowSub: { fontSize: 13, color: '#64748b', marginTop: 4 },
  error: { color: '#b91c1c', padding: 16 },
  empty: { textAlign: 'center', color: '#64748b', marginTop: 24 },
});
