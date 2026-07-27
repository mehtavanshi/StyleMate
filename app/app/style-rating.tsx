import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";

import { Sparkles, Star } from "../lib/icons";
import {
  consentApi,
  ConsentStatus,
  DEMO_USER_ID,
  fashionRatingApi,
  FashionRating,
} from "../lib/api";
import { BASE_URL } from "../config/api";
import { resolvePhotoUrl } from "../lib/constants";
import useHardwareBack from "../lib/useHardwareBack";
import BackButton from "../components/BackButton";
import {
  borderRadius as br,
  colors,
  fontSize,
  fontWeight,
  shadow,
  spacing,
} from "../theme/tokens";

const SCORE_LABELS: Record<string, string> = {
  overall_style: "Overall style",
  color_harmony: "Color harmony",
  fit: "Fit",
  occasion_match: "Occasion match",
  silhouette_balance: "Silhouette balance",
};

function scoreColor(score: number): string {
  if (score >= 7.5) return colors.score.high;
  if (score >= 5) return colors.score.mid;
  return colors.score.low;
}

export default function StyleRatingScreen() {
  const navigation = useNavigation();
  const [consent, setConsent] = useState<ConsentStatus | null>(null);
  const [rating, setRating] = useState<FashionRating | null>(null);
  const [loading, setLoading] = useState(false);
  const [openSuggestion, setOpenSuggestion] = useState<number | null>(null);

  const handleBack = useCallback(() => {
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      router.replace("/(tabs)");
    }
    return true;
  }, [navigation]);

  useHardwareBack(handleBack);

  useEffect(() => {
    consentApi.getStatus(DEMO_USER_ID).then(setConsent).catch(() => setConsent(null));
  }, []);

  const rate = useCallback(async () => {
    setLoading(true);
    setRating(null);
    try {
      setRating(await fashionRatingApi.rate());
    } catch (e: any) {
      setRating({ available: false, message: e.message });
    } finally {
      setLoading(false);
    }
  }, []);

  const photoUrl = resolvePhotoUrl(consent?.photo_url ?? null, BASE_URL);

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <BackButton title="Rate My Style" />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {photoUrl ? (
          <Image source={{ uri: photoUrl }} style={styles.photo} resizeMode="cover" />
        ) : (
          <View style={styles.photoEmpty}>
            <Text style={styles.emptyText}>
              {consent?.photo_consent
                ? "Add a full-body photo to get a style rating."
                : "Give photo consent, then add a photo to get a style rating."}
            </Text>
            <TouchableOpacity
              style={styles.primaryBtn}
              onPress={() => router.push(consent?.photo_consent ? "/capture?returnTo=/style-rating" : "/consent?returnTo=/style-rating")}
            >
              <Text style={styles.primaryBtnText}>
                {consent?.photo_consent ? "Take my photo" : "Give consent"}
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {photoUrl && (
          <TouchableOpacity
            style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]}
            onPress={rate}
            disabled={loading}
          >
            <View style={styles.btnInner}>
              <Sparkles size={16} color={colors.text.white} strokeWidth={1.5} />
              <Text style={styles.primaryBtnText}>
                {loading ? "Analyzing..." : rating ? "Rate Again" : "Rate My Style"}
              </Text>
            </View>
          </TouchableOpacity>
        )}

        {loading && (
          <View style={styles.loadingBox} accessibilityRole="progressbar">
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.loadingText}>Asking the stylist...</Text>
          </View>
        )}

        {rating && !rating.available && (
          <Text style={styles.unavailable}>{rating.message}</Text>
        )}

        {rating?.available && rating.scores && (
          <>
            <View style={styles.scoreRing}>
              <Text style={[styles.scoreBig, { color: scoreColor(rating.average_score ?? 0) }]}>
                {rating.average_score?.toFixed(1)}
              </Text>
              <Text style={styles.scoreOutOf}>/ 10</Text>
            </View>

            {Object.entries(rating.scores).map(([key, value]) => (
              <View key={key} style={styles.scoreRow}>
                <View style={styles.scoreLabelRow}>
                  <Text style={styles.scoreLabel}>{SCORE_LABELS[key] ?? key}</Text>
                  <Text style={[styles.scoreValue, { color: scoreColor(value.score) }]}>
                    {value.score.toFixed(1)}
                  </Text>
                </View>
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.barFill,
                      { width: `${value.score * 10}%`, backgroundColor: scoreColor(value.score) },
                    ]}
                  />
                </View>
                {!!value.reason && <Text style={styles.scoreReason}>{value.reason}</Text>}
              </View>
            ))}

            {!!rating.vibe_tags?.length && (
              <View style={styles.tagRow}>
                {rating.vibe_tags.map((tag) => (
                  <View key={tag} style={styles.tag}>
                    <Text style={styles.tagText}>{tag}</Text>
                  </View>
                ))}
              </View>
            )}

            {!!rating.suggestions?.length && (
              <>
                <Text style={styles.sectionLabel}>Improvements</Text>
                {rating.suggestions.map((s, i) => (
                  <TouchableOpacity
                    key={i}
                    style={styles.suggestionChip}
                    onPress={() => setOpenSuggestion(openSuggestion === i ? null : i)}
                  >
                    <Star size={14} color={colors.warning} strokeWidth={1.5} />
                    <Text
                      style={styles.suggestionText}
                      numberOfLines={openSuggestion === i ? undefined : 1}
                    >
                      {s}
                    </Text>
                  </TouchableOpacity>
                ))}
              </>
            )}

            {!!rating.primary_colors_detected?.length && (
              <Text style={styles.colorsLine}>
                Colors detected: {rating.primary_colors_detected.join(", ")}
              </Text>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.lg,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { fontSize: fontSize.xl, fontWeight: fontWeight.bold },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  photo: { width: "100%", height: 300, borderRadius: br.md, backgroundColor: "#e0e0e0" },
  photoEmpty: {
    width: "100%",
    padding: spacing.xl,
    borderRadius: br.md,
    backgroundColor: colors.surface,
    alignItems: "center",
    gap: spacing.md,
  },
  emptyText: { fontSize: fontSize.sm, color: colors.text.secondary, textAlign: "center" },
  primaryBtn: {
    marginTop: spacing.lg,
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.md + 2,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
  },
  primaryBtnDisabled: { opacity: 0.6 },
  primaryBtnText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  btnInner: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  loadingBox: { alignItems: "center", gap: spacing.sm, marginTop: spacing.xl },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary },
  unavailable: {
    marginTop: spacing.xl,
    fontSize: fontSize.sm,
    color: colors.text.secondary,
    textAlign: "center",
  },
  scoreRing: {
    marginTop: spacing.xl,
    alignSelf: "center",
    width: 140,
    height: 140,
    borderRadius: 70,
    borderWidth: 6,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    alignItems: "center",
    justifyContent: "center",
    ...shadow.sm,
  },
  scoreBig: { fontSize: fontSize.display, fontWeight: fontWeight.extrabold },
  scoreOutOf: { fontSize: fontSize.xs, color: colors.text.light },
  scoreRow: { marginTop: spacing.lg },
  scoreLabelRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  scoreLabel: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.accent },
  scoreValue: { fontSize: fontSize.sm, fontWeight: fontWeight.bold },
  barTrack: {
    height: 8,
    borderRadius: br.full,
    backgroundColor: "#e6e6e6",
    marginTop: spacing.xs,
    overflow: "hidden",
  },
  barFill: { height: "100%", borderRadius: br.full },
  scoreReason: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },
  tagRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.xl },
  tag: {
    backgroundColor: colors.surface,
    borderRadius: br.full,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tagText: { fontSize: fontSize.xs, color: colors.accent },
  sectionLabel: {
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  suggestionChip: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  suggestionText: { flex: 1, fontSize: fontSize.sm, color: colors.accent, lineHeight: 19 },
  colorsLine: { marginTop: spacing.lg, fontSize: fontSize.xs, color: colors.text.light },
});
