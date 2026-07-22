import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, shadow, spacing } from "../../theme/tokens";
import { router, useFocusEffect } from "expo-router";

import { DEMO_USER_ID, tryOnApi, TryOnJob } from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";
import { X } from "../../lib/icons";

function TryOnResultCard({ item }: { item: TryOnJob }) {
  const [imgFailed, setImgFailed] = useState(false);
  const uri = item.result_image_url
    ? resolvePhotoUrl(item.result_image_url, BASE_URL) ?? undefined
    : undefined;

  return (
    <TouchableOpacity
      style={styles.card}
      activeOpacity={0.8}
      onPress={() => router.push(`/try-on?job_id=${item.job_id}`)}
      accessibilityLabel={`Try-on result from ${item.created_at ? new Date(item.created_at).toLocaleDateString() : "unknown date"}`}
    >
      {uri && !imgFailed ? (
        <Image
          source={{ uri }}
          style={styles.cardImage}
          resizeMode="cover"
          onError={() => setImgFailed(true)}
        />
      ) : (
        <View style={[styles.cardImage, styles.cardPlaceholder]} accessibilityLabel="Try-on image unavailable">
          <Text style={styles.cardPlaceholderText}>?</Text>
        </View>
      )}
      <View style={styles.cardInfo}>
        {item.latency_ms != null && (
          <Text style={styles.cardMeta}>
            Rendered in {(item.latency_ms / 1000).toFixed(1)}s
          </Text>
        )}
        <Text style={styles.cardDate}>
          {item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}
        </Text>
      </View>
    </TouchableOpacity>
  );
}

export default function MyTryOnsScreen() {
  const [results, setResults] = useState<TryOnJob[]>([]);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      setLoading(true);
      tryOnApi
        .results(DEMO_USER_ID)
        .then((data) => {
          if (!cancelled) setResults(data);
        })
        .catch(() => {})
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
      return () => {
        cancelled = true;
      };
    }, [])
  );

  if (loading) {
    return (
      <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Loading your try-ons">
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Loading try-ons...</Text>
      </View>
    );
  }

  if (results.length === 0) {
    return (
      <View style={styles.center} accessibilityLabel="No try-ons yet">
        <Text style={styles.emptyTitle}>No Try-Ons Yet</Text>
        <Text style={styles.emptyText}>
          Head to the Outfits tab and tap &quot;Try It On&quot; on any outfit to see how it looks on you!
        </Text>
      </View>
    );
  }

  const completedResults = results.filter((r) => r.status === "completed");
  const failedResults = results.filter((r) => r.status === "failed");

  const renderResult = ({ item }: { item: TryOnJob }) => (
    <TryOnResultCard item={item} />
  );

  const renderFailed = ({ item }: { item: TryOnJob }) => (
    <View style={[styles.card, styles.cardFailed]} accessibilityLabel={`Failed try-on: ${item.error_message || "Unknown error"}`}>
      <View style={styles.cardImage}>
        <X size={32} color="#E74C3C" strokeWidth={1.5} />
      </View>
      <View style={styles.cardInfo}>
        <Text style={styles.failedText} numberOfLines={2}>
          {item.error_message || "Failed"}
        </Text>
        <Text style={styles.cardDate}>
          {item.created_at ? new Date(item.created_at).toLocaleDateString() : ""}
        </Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      {completedResults.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Successful Try-Ons</Text>
          <FlatList
            data={completedResults}
            keyExtractor={(item) => item.job_id}
            renderItem={renderResult}
            numColumns={2}
            contentContainerStyle={styles.grid}
            showsVerticalScrollIndicator={false}
          />
        </>
      )}
      {failedResults.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Failed</Text>
          <FlatList
            data={failedResults}
            keyExtractor={(item) => item.job_id}
            renderItem={renderFailed}
            numColumns={2}
            contentContainerStyle={styles.grid}
            showsVerticalScrollIndicator={false}
          />
        </>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm },
  emptyTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.semibold, marginBottom: spacing.sm },
  emptyText: { fontSize: fontSize.sm, color: colors.text.tertiary, textAlign: "center", lineHeight: 22, paddingHorizontal: spacing.xl },

  sectionTitle: {
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.sm,
  },
  grid: { paddingHorizontal: spacing.md, paddingBottom: spacing.xl },

  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    overflow: "hidden",
    margin: spacing.xs,
    ...shadow.sm,
  },
  cardFailed: { opacity: 0.6 },
  cardImage: {
    width: "100%",
    aspectRatio: 3 / 4,
    backgroundColor: "#e0e0e0",
  },
  cardPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  cardPlaceholderText: { fontSize: fontSize.xxl + 4, fontWeight: fontWeight.bold, color: colors.text.light },
  failedIcon: { fontSize: fontSize.xxl + 4, color: colors.danger, fontWeight: fontWeight.bold },
  cardInfo: { padding: spacing.sm },
  cardMeta: { fontSize: fontSize.xs - 1, color: colors.text.tertiary },
  cardDate: { fontSize: fontSize.xs - 1, color: colors.text.muted, marginTop: spacing.xs },
  failedText: { fontSize: fontSize.xs, color: colors.danger, lineHeight: 16 },
});
