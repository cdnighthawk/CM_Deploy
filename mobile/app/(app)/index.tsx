import { Link, Stack } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { displayName, useAuth } from '@/src/auth/AuthContext';

export default function HomeScreen() {
  const { user, signOut } = useAuth();

  return (
    <View style={styles.root}>
      <Stack.Screen
        options={{
          title: 'USIS CM',
          headerRight: () => (
            <Pressable onPress={signOut} style={styles.headerBtn}>
              <Text style={styles.headerBtnText}>Sign out</Text>
            </Pressable>
          ),
        }}
      />
      <Text style={styles.greeting}>Hello, {user ? displayName(user) : 'there'}</Text>
      <Text style={styles.hint}>Field app — projects and offline drawings.</Text>

      <Link href="/(app)/projects" asChild>
        <Pressable style={styles.primaryCard}>
          <Text style={styles.cardTitle}>Projects</Text>
          <Text style={styles.cardSub}>Browse jobs and open drawing sets</Text>
        </Pressable>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, padding: 20, backgroundColor: '#f8fafc' },
  greeting: { fontSize: 22, fontWeight: '700', color: '#0f172a', marginBottom: 8 },
  hint: { fontSize: 14, color: '#64748b', marginBottom: 24 },
  primaryCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: '#e2e8f0',
  },
  cardTitle: { fontSize: 18, fontWeight: '600', color: '#1e40af' },
  cardSub: { fontSize: 14, color: '#64748b', marginTop: 4 },
  headerBtn: { marginRight: 8, padding: 8 },
  headerBtnText: { color: '#1d4ed8', fontSize: 15 },
});
