import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  Image,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { router, useLocalSearchParams } from "expo-router";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";

import { calendarApi, CalendarEntry, tryOnApi, TryOnJob } from "../lib/api";
import { resolvePhotoUrl } from "../lib/constants";
import { BASE_URL } from "../config/api";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../theme/tokens";

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
  const [showCalendarModal, setShowCalendarModal] = useState(false);
  const [calendarDate, setCalendarDate] = useState(
    new Date().toISOString().slice(0, 10)
  );
  const [savingToCalendar, setSavingToCalendar] = useState(false);
  const [savedToCalendar, setSavedToCalendar] = useState(false);

  const insets = useSafeAreaInsets();

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
            id: 0,
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
        id: 0,
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

  const handleSaveToCalendar = async () => {
    if (!job?.result_image_url) return;
    setSavingToCalendar(true);
    try {
      let entry = await calendarApi.create({ date: calendarDate });
      if (!entry) {
        Alert.alert("Error", "Could not create calendar entry");
        return;
      }
      await calendarApi.linkTryOnImage(entry.id, job.id);
      setSavedToCalendar(true);
      setShowCalendarModal(false);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Could not save to calendar");
    } finally {
      setSavingToCalendar(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Generating your virtual try-on">
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>{TRYON_LOADING_MESSAGES[messageIndex]}</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (!job) {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.center} accessibilityLabel="No try-on result found">
          <Text style={styles.errorText}>No try-on result found.</Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
            <Text style={styles.primaryBtnText}>Back to Outfits</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ── Rate limit ──
  if (job.error_type === "rate_limit") {
    const resetTime = job.rate_limit_resets_at
      ? new Date(job.rate_limit_resets_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : "midnight";
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.center} accessibilityLabel="Daily try-on limit reached">
          <Text style={styles.errorTitle}>Daily Limit Reached</Text>
          <Text style={styles.errorText}>
            {"You've used all your try-ons for today — they'll refresh at " + resetTime + "."}
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
            <Text style={styles.primaryBtnText}>Back to Outfits</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  // ── Bad photo ──
  if (job.error_type === "bad_photo") {
    return (
      <SafeAreaView style={{ flex: 1 }}>
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
      </SafeAreaView>
    );
  }

  // ── Failed ──
  if (job.status === "failed") {
    return (
      <SafeAreaView style={{ flex: 1 }}>
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
      </SafeAreaView>
    );
  }

  // ── Completed ──
  const imageUri = job.result_image_url
    ? resolvePhotoUrl(job.result_image_url, BASE_URL) ?? undefined
    : undefined;

  return (
    <SafeAreaView style={[styles.resultContainer, { paddingTop: insets.top }]} accessibilityLabel="Virtual try-on result">
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

        <TouchableOpacity
          style={[styles.actionBtn, styles.calendarBtn, savedToCalendar && styles.actionBtnDone]}
          onPress={() => setShowCalendarModal(true)}
          disabled={savedToCalendar}
          accessibilityLabel="Save to calendar"
        >
          <Text style={[styles.actionBtnText, savedToCalendar && styles.actionBtnTextDone]}>
            {savedToCalendar ? "Saved" : "Calendar"}
          </Text>
        </TouchableOpacity>
      </View>

      <TouchableOpacity style={styles.secondaryBtn} onPress={() => router.back()} accessibilityLabel="Go back to outfits">
        <Text style={styles.secondaryBtnText}>Back to Outfits</Text>
      </TouchableOpacity>

      <Modal
        visible={showCalendarModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowCalendarModal(false)}
      >
        <View style={styles.calendarModalOverlay}>
          <View style={styles.calendarModalContent}>
            <Text style={styles.calendarModalTitle}>Save to Calendar</Text>
            <Text style={styles.calendarModalLabel}>Date</Text>
            <TextInput
              style={styles.calendarDateInput}
              value={calendarDate}
              onChangeText={setCalendarDate}
              placeholder="YYYY-MM-DD"
            />
            <View style={styles.calendarModalActions}>
              <TouchableOpacity
                style={[styles.calendarModalBtn, styles.calendarModalCancel]}
                onPress={() => setShowCalendarModal(false)}
                disabled={savingToCalendar}
              >
                <Text style={styles.calendarModalCancelText}>Cancel</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.calendarModalBtn, styles.calendarModalSave]}
                onPress={handleSaveToCalendar}
                disabled={savingToCalendar}
              >
                {savingToCalendar ? (
                  <ActivityIndicator size="small" color="#fff" />
                ) : (
                  <Text style={styles.calendarModalSaveText}>Save</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xxl,
    backgroundColor: colors.background,
  },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm + 6 },
  errorTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.bold, marginBottom: spacing.sm, textAlign: "center" },
  errorText: {
    fontSize: fontSize.sm,
    color: colors.danger,
    textAlign: "center",
    marginBottom: spacing.xl,
    lineHeight: 22,
    paddingHorizontal: spacing.xl,
  },

  resultContainer: {
    flex: 1,
    backgroundColor: colors.background,
  },
  resultHeader: {
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
  },
  title: { fontSize: fontSize.xxl - 2, fontWeight: fontWeight.bold, marginBottom: spacing.xs },
  subtitle: { fontSize: fontSize.sm, color: colors.text.tertiary },

  imageWrapper: {
    flex: 1,
    marginHorizontal: spacing.lg,
    borderRadius: br.md + 4,
    backgroundColor: "#e0e0e0",
    marginBottom: spacing.sm,
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
    borderRadius: br.md + 4,
    backgroundColor: "#e0e0e0",
  },
  imagePlaceholder: {
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#e0e0e0",
  },
  imagePlaceholderText: { fontSize: fontSize.sm, color: colors.text.light },

  meta: { fontSize: fontSize.xs, color: colors.text.light, textAlign: "center", marginBottom: spacing.sm + 6 },

  actionsRow: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm + 6,
  },
  actionBtn: {
    flex: 1,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  actionBtnDone: { backgroundColor: colors.success },
  actionBtnLoading: { opacity: 0.6 },
  saveBtn: { backgroundColor: colors.accent },
  shareBtn: { backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.accent },
  actionBtnText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  actionBtnTextDark: { color: colors.accent, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  actionBtnTextDone: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  calendarBtn: { backgroundColor: colors.success },

  primaryBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
    minWidth: 200,
    marginBottom: spacing.sm,
  },
  primaryBtnText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  secondaryBtn: {
    borderRadius: br.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
    minWidth: 200,
    marginBottom: spacing.xl,
    alignSelf: "center",
  },
  secondaryBtnText: { color: "#666", fontSize: fontSize.sm + 1, fontWeight: fontWeight.semibold },

  calendarModalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
  },
  calendarModalContent: {
    backgroundColor: colors.surface,
    borderRadius: br.lg,
    padding: spacing.xl,
    width: "100%",
    maxWidth: 340,
    gap: spacing.md,
  },
  calendarModalTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.text.primary,
    textAlign: "center",
  },
  calendarModalLabel: {
    fontSize: fontSize.sm + 1,
    fontWeight: fontWeight.semibold,
    color: colors.text.secondary,
  },
  calendarDateInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: br.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm + 2,
    fontSize: fontSize.base,
    color: colors.text.primary,
    backgroundColor: colors.background,
  },
  calendarModalActions: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  calendarModalBtn: {
    flex: 1,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 48,
  },
  calendarModalCancel: {
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.border,
  },
  calendarModalSave: {
    backgroundColor: colors.accent,
  },
  calendarModalCancelText: {
    color: colors.text.secondary,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
  },
  calendarModalSaveText: {
    color: colors.text.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
  },
});
