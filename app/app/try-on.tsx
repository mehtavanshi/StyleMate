import { useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";

import { tryOnApi, TryOnJob } from "../lib/api";
import { resolvePhotoUrl } from "../lib/constants";
import { BASE_URL } from "../config/api";

const POLL_INTERVAL = 2000;

export default function TryOnScreen() {
  const { garment_id } = useLocalSearchParams<{ garment_id?: string }>();
  const [job, setJob] = useState<TryOnJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!garment_id) {
      setError("No garment selected");
      setLoading(false);
      return;
    }

    const gid = parseInt(garment_id, 10);
    if (isNaN(gid)) {
      setError("Invalid garment ID");
      setLoading(false);
      return;
    }

    const startJob = async () => {
      try {
        const result = await tryOnApi.render(gid);
        setJob(result);

        if (result.status === "completed" || result.status === "failed") {
          setLoading(false);
          return;
        }

        pollRef.current = setInterval(async () => {
          try {
            const updated = await tryOnApi.poll(result.job_id);
            setJob(updated);
            if (updated.status === "completed" || updated.status === "failed") {
              if (pollRef.current) clearInterval(pollRef.current);
              setLoading(false);
            }
          } catch {
            if (pollRef.current) clearInterval(pollRef.current);
            setError("Failed to check job status");
            setLoading(false);
          }
        }, POLL_INTERVAL);
      } catch (e: any) {
        setError(e.message);
        setLoading(false);
      }
    };

    startJob();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [garment_id]);

  if (loading && !job) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Starting try-on...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()}>
          <Text style={styles.primaryBtnText}>Go Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isProcessing = job?.status === "pending" || job?.status === "processing";
  const isCompleted = job?.status === "completed";
  const isFailed = job?.status === "failed";

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Virtual Try-On</Text>

      {isProcessing && (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>
            {job?.status === "pending" ? "Queued..." : "Rendering..."}
          </Text>
        </View>
      )}

      {isCompleted && job?.result_image_url && (
        <>
          <Text style={styles.subtitle}>Here's how it looks on you!</Text>
          <Image
            source={{ uri: resolvePhotoUrl(job.result_image_url, BASE_URL) ?? undefined }}
            style={styles.resultImage}
            resizeMode="contain"
          />
          {job.latency_ms != null && (
            <Text style={styles.meta}>Rendered in {(job.latency_ms / 1000).toFixed(1)}s</Text>
          )}
        </>
      )}

      {isFailed && (
        <View style={styles.center}>
          <Text style={styles.errorText}>
            {job?.error_message || "Try-on failed. Please try again."}
          </Text>
        </View>
      )}

      <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.back()}>
        <Text style={styles.secondaryBtnText}>Done</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, backgroundColor: "#f5f5f5", padding: 20, alignItems: "center" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30, backgroundColor: "#f5f5f5" },
  title: { fontSize: 22, fontWeight: "700", marginBottom: 4, marginTop: 20 },
  subtitle: { fontSize: 14, color: "#888", marginBottom: 20 },
  loadingText: { fontSize: 14, color: "#888", marginTop: 14 },
  errorText: { fontSize: 14, color: "#E74C3C", textAlign: "center", marginBottom: 20, lineHeight: 20 },
  resultImage: {
    width: "100%",
    height: 500,
    borderRadius: 14,
    backgroundColor: "#e0e0e0",
    marginBottom: 10,
  },
  meta: { fontSize: 12, color: "#999", marginBottom: 20 },
  primaryBtn: {
    backgroundColor: "#333",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: "center",
    minWidth: 200,
    marginBottom: 10,
  },
  primaryBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  secondaryBtn: {
    borderRadius: 12,
    paddingVertical: 12,
    paddingHorizontal: 24,
    alignItems: "center",
    minWidth: 200,
    marginBottom: 20,
  },
  secondaryBtnText: { color: "#666", fontSize: 15, fontWeight: "600" },
});
