import { Link, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

import { ApiError } from '@/src/api/client';
import { fetchProject } from '@/src/api/projects';

export default function ProjectDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');

  useEffect(() => {
    if (!id) return;
    fetchProject(id)
      .then((p) => setName(p.name))
      .catch((e) => setError(e instanceof ApiError ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <View style={styles.root}>
      <Stack.Screen options={{ title: name || 'Project' }} />
      {loading ? (
        <ActivityIndicator style={{ marginTop: 24 }} />
      ) : error ? (
        <Text style={styles.error}>{error}</Text>
      ) : (
        <>
          <Text style={styles.title}>{name}</Text>
          <Link href={`/(app)/projects/${id}/drawings`} asChild>
            <Pressable style={styles.card}>
              <Text style={styles.cardTitle}>Drawings</Text>
              <Text style={styles.cardSub}>View and cache drawing sets for offline use</Text>
            </Pressable>
          </Link>
          <View style={[styles.card, styles.cardDisabled]}>
            <Text style={styles.cardTitle}>Schedule</Text>
            <Text style={styles.cardSub}>Coming soon</Text>
          </View>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: 16, backgroundColor: '#f8fafc' },
  title: { fontSize: 20, fontWeight: '700', marginBottom: 16, color: '#0f172a' },
  card: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardDisabled: { opacity: 0.65 },
  cardTitle: { fontSize: 17, fontWeight: '600', color: '#1e40af' },
  cardSub: { fontSize: 13, color: '#64748b', marginTop: 4 },
  error: { color: '#b91c1c' },
});
