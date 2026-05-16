import { Redirect, Stack } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';

import { useAuth } from '@/src/auth/AuthContext';

export default function AppLayout() {
  const { ready, user } = useAuth();

  if (!ready) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  if (!user) {
    return <Redirect href="/(auth)/login" />;
  }

  return (
    <Stack>
      <Stack.Screen name="index" options={{ title: 'Home' }} />
      <Stack.Screen name="projects/index" options={{ title: 'Projects' }} />
      <Stack.Screen name="projects/[id]/index" options={{ title: 'Project' }} />
      <Stack.Screen name="projects/[id]/drawings" options={{ title: 'Drawings' }} />
      <Stack.Screen
        name="projects/[id]/viewer"
        options={{ title: 'Sheet', presentation: 'modal' }}
      />
    </Stack>
  );
}
