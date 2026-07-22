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
import { router, useFocusEffect } from "expo-router";

import { DEMO_USER_ID, tryOnApi, TryOnJob } from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";

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
        <Text style={styles.failedIcon}>✕</Text>
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
    <View style={styles.container}>
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30 },
  loadingText: { fontSize: 14, color: "#888", marginTop: 10 },
  emptyTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  emptyText: { fontSize: 14, color: "#888", textAlign: "center", lineHeight: 22, paddingHorizontal: 20 },

  sectionTitle: {
    fontSize: 16,
    fontWeight: "700",
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
  },
  grid: { paddingHorizontal: 12, paddingBottom: 20 },

  card: {
    flex: 1,
    backgroundColor: "#fff",
    borderRadius: 12,
    overflow: "hidden",
    margin: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
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
  cardPlaceholderText: { fontSize: 28, fontWeight: "700", color: "#999" },
  failedIcon: { fontSize: 28, color: "#E74C3C", fontWeight: "700" },
  cardInfo: { padding: 8 },
  cardMeta: { fontSize: 11, color: "#888" },
  cardDate: { fontSize: 11, color: "#aaa", marginTop: 2 },
  failedText: { fontSize: 12, color: "#E74C3C", lineHeight: 16 },
});
