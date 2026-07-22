import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  AppState,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";

import { tryOnApi, TryOnJob } from "../lib/api";
import { resolvePhotoUrl } from "../lib/constants";
import { BASE_URL } from "../config/api";

const TRYON_LOADING_MESSAGES = [
  "Fitting the garment...",
  "Matching your lighting...",
  "Almost there...",
  "Tailoring the fit...",
  "Blending colors...",
];

export default function TryOnScreen() {
  const { job_id } = useLocalSearchParams<{ job_id?: string }>();
  const [job, setJob] = useState<TryOnJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [saved, setSaved] = useState(false);
  const [messageIndex, setMessageIndex] = useState(0);
  const [imageLoadFailed, setImageLoadFailed] = useState(false);

  const messageInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollInterval = useRef<ReturnType<typeof setInterval> | null>(null);
  const appStateRef = useRef(AppState.currentState);
  const jobRef = useRef(job);
  jobRef.current = job;

  useEffect(() => {
    messageInterval.current = setInterval(() => {
      setMessageIndex((prev) => (prev + 1) % TRYON_LOADING_MESSAGES.length);
    }, 3000);
    return () => {
      if (messageInterval.current) clearInterval(messageInterval.current);
    };
  }, []);

  const clearPolling = useCallback(() => {
    if (pollInterval.current) {
      clearInterval(pollInterval.current);
      pollInterval.current = null;
    }
  }, []);

  const pollJob = useCallback(
    (id: string) => {
      clearPolling();
      pollInterval.current = setInterval(async () => {
        try {
          const updated = await tryOnApi.poll(id);
          if (updated.status === "completed" || updated.status === "failed") {
            clearPolling();
            if (messageInterval.current) clearInterval(messageInterval.current);
            setJob(updated);
            setLoading(false);
          }
        } catch {
          clearPolling();
          if (messageInterval.current) clearInterval(messageInterval.current);
          setJob({
            job_id: id,
            status: "failed",
            result_image_url: null,
            error_message: "Could not load try-on result",
            error_type: null,
            model_used: null,
            latency_ms: null,
            created_at: "",
          });
          setLoading(false);
        }
      }, 2000);
    },
    [clearPolling]
  );

  const fetchJob = useCallback(async () => {
    if (!job_id) {
      setLoading(false);
      return;
    }
    try {
      const result = await tryOnApi.poll(job_id);
      setJob(result);
      if (result.status === "pending" || result.status === "processing") {
        pollJob(job_id);
      } else {
        setLoading(false);
      }
    } catch {
      setJob({
        job_id,
        status: "failed",
        result_image_url: null,
        error_message: "Could not load try-on result",
        error_type: null,
        model_used: null,
        latency_ms: null,
        created_at: "",
      });
      setLoading(false);
    } finally {
      if (messageInterval.current) clearInterval(messageInterval.current);
    }
  }, [job_id, pollJob]);

  useEffect(() => {
    fetchJob();
    return () => clearPolling();
  }, [fetchJob, clearPolling]);

  // AppState listener: re-poll immediately when app comes to foreground
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasBg = appStateRef.current.match(/inactive|background/);
      appStateRef.current = nextState;

      if (wasBg && nextState === "active") {
        const current = jobRef.current;
        if (
          current &&
          job_id &&
          (current.status === "pending" || current.status === "processing")
        ) {
          // App just came to foreground — poll immediately
          tryOnApi
            .poll(job_id)
            .then((updated) => {
              if (updated.status === "completed" || updated.status === "failed") {
                clearPolling();
                if (messageInterval.current) clearInterval(messageInterval.current);
                setJob(updated);
                setLoading(false);
              }
            })
            .catch(() => {});
        }
      }
    });

    return () => subscription.remove();
  }, [job_id, clearPolling]);

  const handleSave = async () => {
    if (!job?.result_image_url) return;
    setSaving(true);
    try {
      const MediaLibrary = await import("expo-media-library");
      const { status } = await MediaLibrary.requestPermissionsAsync();
      if (status !== "granted") {
        setSaving(false);
        return;
      }
      const uri = resolvePhotoUrl(job.result_image_url, BASE_URL) ?? job.result_image_url;
      await MediaLibrary.saveToLibraryAsync(uri);
      setSaved(true);
    } catch {
      setSaving(false);
    } finally {
      setSaving(false);
    }
  };

  const handleShare = async () => {
    if (!job?.result_image_url) return;
    setSharing(true);
    try {
      const Sharing = await import("expo-sharing");
      const uri = resolvePhotoUrl(job.result_image_url, BASE_URL) ?? job.result_image_url;
      const result = await manipulateAsync(uri, [], { format: SaveFormat.PNG });
      await Sharing.shareAsync(result.uri, {
        mimeType: "image/png",
        dialogTitle: "Share your try-on from StyleMate",
      });
    } catch {
      // Share cancelled or failed
    } finally {
      setSharing(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Generating your virtual try-on">
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>{TRYON_LOADING_MESSAGES[messageIndex]}</Text>
      </View>
    );
  }

  if (!job) {
    return (
      <View style={styles.center} accessibilityLabel="No try-on result found">
        <Text style={styles.errorText}>No try-on result found.</Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
          <Text style={styles.primaryBtnText}>Back to Outfits</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── Rate limit ──
  if (job.error_type === "rate_limit") {
    const resetTime = job.rate_limit_resets_at
      ? new Date(job.rate_limit_resets_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "midnight";
    return (
      <View style={styles.center} accessibilityLabel="Daily try-on limit reached">
        <Text style={styles.errorTitle}>Daily Limit Reached</Text>
        <Text style={styles.errorText}>
          {"You've used all your try-ons for today — they'll refresh at " + resetTime + "."}
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
          <Text style={styles.primaryBtnText}>Back to Outfits</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── Bad photo ──
  if (job.error_type === "bad_photo") {
    return (
      <View style={styles.center} accessibilityLabel="Photo could not be processed">
        <Text style={styles.errorTitle}>Photo Not Usable</Text>
        <Text style={styles.errorText}>
          The provider couldn&apos;t process this photo. Try retaking with even lighting and a plain
          background.
        </Text>
        <TouchableOpacity
          style={styles.primaryBtn}
          onPress={() => router.push("/capture")}
          accessibilityLabel="Retake your photo"
        >
          <Text style={styles.primaryBtnText}>Retake Photo</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
          <Text style={styles.secondaryBtnText}>Back to Outfits</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── Failed ──
  if (job.status === "failed") {
    return (
      <View style={styles.center} accessibilityLabel="Try-on failed">
        <Text style={styles.errorTitle}>Something Went Wrong</Text>
        <Text style={styles.errorText}>
          {job.error_message || "The try-on failed. Please try again."}
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={() => fetchJob()} accessibilityLabel="Retry try-on">
          <Text style={styles.primaryBtnText}>Retry</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
          <Text style={styles.secondaryBtnText}>Back to Outfits</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ── Completed ──
  const imageUri = job.result_image_url
    ? resolvePhotoUrl(job.result_image_url, BASE_URL) ?? undefined
    : undefined;

  return (
    <View style={styles.resultContainer} accessibilityLabel="Virtual try-on result">
      <View style={styles.resultHeader}>
        <Text style={styles.title} accessibilityRole="header">Virtual Try-On</Text>
        <Text style={styles.subtitle}>Here&apos;s how it looks on you!</Text>
      </View>

      <ScrollView
        style={styles.imageWrapper}
        contentContainerStyle={styles.imageScrollContent}
        maximumZoomScale={3}
        minimumZoomScale={1}
        showsHorizontalScrollIndicator={false}
        showsVerticalScrollIndicator={false}
      >
        {imageUri && !imageLoadFailed ? (
          <Image
            source={{ uri: imageUri }}
            style={styles.resultImage}
            resizeMode="contain"
            accessibilityLabel="Try-on result image"
            onError={() => setImageLoadFailed(true)}
          />
        ) : (
          <View style={[styles.resultImage, styles.imagePlaceholder]} accessibilityLabel="Image unavailable">
            <Text style={styles.imagePlaceholderText}>Image unavailable</Text>
          </View>
        )}
      </ScrollView>

      {job.latency_ms != null && (
        <Text style={styles.meta}>Rendered in {(job.latency_ms / 1000).toFixed(1)}s</Text>
      )}

      <View style={styles.actionsRow}>
        <TouchableOpacity
          style={[styles.actionBtn, styles.saveBtn, saved && styles.actionBtnDone]}
          onPress={handleSave}
          disabled={saving || saved}
          accessibilityLabel={saved ? "Image saved to library" : "Save image to library"}
        >
          {saving ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <Text style={styles.actionBtnText}>{saved ? "Saved" : "Save"}</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionBtn, styles.shareBtn, sharing && styles.actionBtnLoading]}
          onPress={handleShare}
          disabled={sharing}
          accessibilityLabel="Share try-on image"
        >
          {sharing ? (
            <ActivityIndicator size="small" color="#333" />
          ) : (
            <Text style={styles.actionBtnTextDark}>Share</Text>
          )}
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
        <Text style={styles.secondaryBtnText}>Back to Outfits</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: 30,
    backgroundColor: "#f5f5f5",
  },
  loadingText: { fontSize: 14, color: "#888", marginTop: 14 },
  errorTitle: { fontSize: 18, fontWeight: "700", marginBottom: 10, textAlign: "center" },
  errorText: {
    fontSize: 14,
    color: "#E74C3C",
    textAlign: "center",
    marginBottom: 20,
    lineHeight: 22,
    paddingHorizontal: 20,
  },

  resultContainer: {
    flex: 1,
    backgroundColor: "#f5f5f5",
    paddingTop: 60,
  },
  resultHeader: {
    paddingHorizontal: 20,
    marginBottom: 10,
  },
  title: { fontSize: 22, fontWeight: "700", marginBottom: 4 },
  subtitle: { fontSize: 14, color: "#888" },

  imageWrapper: {
    flex: 1,
    marginHorizontal: 16,
    borderRadius: 14,
    backgroundColor: "#e0e0e0",
    marginBottom: 10,
    overflow: "hidden",
  },
  imageScrollContent: {
    flexGrow: 1,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 300,
  },
  resultImage: {
    width: 300,
    height: 400,
    borderRadius: 14,
    backgroundColor: "#e0e0e0",
  },
  imagePlaceholder: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#e0e0e0",
  },
  imagePlaceholderText: { fontSize: 14, color: "#999" },

  meta: { fontSize: 12, color: "#999", textAlign: "center", marginBottom: 14 },

  actionsRow: {
    flexDirection: "row",
    gap: 12,
    paddingHorizontal: 20,
    marginBottom: 14,
  },
  actionBtn: {
    flex: 1,
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  actionBtnDone: { backgroundColor: "#2ECC71" },
  actionBtnLoading: { opacity: 0.6 },
  saveBtn: { backgroundColor: "#333" },
  shareBtn: { backgroundColor: "#fff", borderWidth: 1.5, borderColor: "#333" },
  actionBtnText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  actionBtnTextDark: { color: "#333", fontSize: 16, fontWeight: "700" },

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
    alignSelf: "center",
  },
  secondaryBtnText: { color: "#666", fontSize: 15, fontWeight: "600" },
});
