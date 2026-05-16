import { Stack, useLocalSearchParams } from 'expo-router';
import { StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';

export default function PdfViewerScreen() {
  const { localPath, title } = useLocalSearchParams<{
    localPath: string;
    title?: string;
  }>();

  const uri = localPath?.startsWith('file://') ? localPath : `file://${localPath}`;

  return (
    <View style={styles.root}>
      <Stack.Screen options={{ title: title || 'Sheet' }} />
      {localPath ? (
        <WebView
          source={{ uri }}
          style={styles.webview}
          originWhitelist={['*']}
          allowFileAccess
          allowUniversalAccessFromFileURLs
        />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  webview: { flex: 1 },
});
