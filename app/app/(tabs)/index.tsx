import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, shadow, spacing } from "../../theme/tokens";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";
import { Settings, Star } from "../../lib/icons";

import {
  CalendarEntry,
  calendarApi,
  clothingApi,
  ConsentStatus,
  DEMO_USER_ID,
  consentApi,
  outfitApi,
  OutfitSuggestion,
  uploadApi,
} from "../../lib/api";
import { resolvePhotoUrl, MAX_LONG_EDGE_PX, JPEG_QUALITY } from "../../lib/constants";
import { BASE_URL } from "../../config/api";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import TryOnUsageBadge from "../../components/TryOnUsageBadge";
import Avatar from "../../components/Avatar";
import { useTabScreenPadding } from "../../lib/useTabScreenPadding";

const ONBOARDING_FLAG = "onboarding_complete";

export default function HomeScreen() {
  const [checked, setChecked] = useState(false);
  const [seen, setSeen] = useState(false);
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [todaysOutfit, setTodaysOutfit] = useState<OutfitSuggestion | null>(null);
  const [outfitLoading, setOutfitLoading] = useState(true);
  const [wardrobeStats, setWardrobeStats] = useState<Record<string, number>>({});
  const [nextCalendarEntry, setNextCalendarEntry] = useState<CalendarEntry | null>(null);

  const loadHomeData = useCallback(async () => {
    setOutfitLoading(true);
    try {
      const [outfits, items, entries] = await Promise.all([
        outfitApi.suggest({ limit: 1 }),
        clothingApi.list(),
        calendarApi.list({ start_date: new Date().toISOString().split("T")[0] }),
      ]);
      if (outfits.length > 0) setTodaysOutfit(outfits[0]);
      const stats: Record<string, number> = {};
      for (const item of items) {
        stats[item.category] = (stats[item.category] || 0) + 1;
      }
      setWardrobeStats(stats);
      const upcoming = entries.find(
        (e) => new Date(e.date) >= new Date(new Date().toDateString()),
      );
      setNextCalendarEntry(upcoming || null);
    } catch {
      // silently fail
    } finally {
      setOutfitLoading(false);
    }
  }, []);

  useEffect(() => {
    AsyncStorage.getItem(ONBOARDING_FLAG)
      .then((v) => setSeen(!!v))
      .finally(() => setChecked(true));
  }, []);

  useEffect(() => {
    consentApi
      .getStatus(DEMO_USER_ID)
      .then((s) => setConsentStatus(s))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadHomeData();
  }, [loadHomeData]);

  const handleDeletePhoto = () => {
    Alert.alert(
      "Delete my photo",
      "This can't be undone. You'll need to upload a new photo to use Try It On.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await consentApi.deletePhoto(DEMO_USER_ID);
              setConsentStatus((prev) =>
                prev ? { ...prev, photo_url: null } : null
              );
            } catch {
              Alert.alert("Error", "Could not delete photo. Please try again.");
            }
          },
        },
      ],
    );
  };

  const handleAvatarPress = () => {
    Alert.alert("Profile Photo", "Choose an option", [
      { text: "Choose from Library", onPress: handlePickFromLibrary },
      { text: "Take Photo", onPress: handleTakePhoto },
      ...(consentStatus?.photo_url
        ? [{ text: "Remove Photo", style: "destructive" as const, onPress: handleRemovePhoto }]
        : []),
      { text: "Cancel", style: "cancel" },
    ]);
  };

  const handlePickFromLibrary = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission needed", "Please grant photo library access.");
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 1,
    });
    if (result.canceled || !result.assets?.[0]) return;
    await uploadAndSetPhoto(result.assets[0].uri);
  };

  const handleTakePhoto = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      Alert.alert("Permission needed", "Please grant camera access.");
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      quality: 1,
    });
    if (result.canceled || !result.assets?.[0]) return;
    await uploadAndSetPhoto(result.assets[0].uri);
  };

  const uploadAndSetPhoto = async (uri: string) => {
    try {
      const manipulated = await ImageManipulator.manipulate(uri)
        .resize({ width: MAX_LONG_EDGE_PX })
        .renderAsync();
      const compressed = await manipulated.saveAsync({
        compress: JPEG_QUALITY,
        format: SaveFormat.JPEG,
      });
      const { image_url } = await uploadApi.uploadImage(
        compressed.uri,
        "photo.jpg",
        "image/jpeg",
      );
      const updated = await consentApi.setPhoto(DEMO_USER_ID, image_url);
      setConsentStatus(updated);
    } catch {
      Alert.alert("Error", "Could not update photo. Please try again.");
    }
  };

  const handleRemovePhoto = async () => {
    try {
      await consentApi.deletePhoto(DEMO_USER_ID);
      setConsentStatus((prev) => (prev ? { ...prev, photo_url: null } : null));
    } catch {
      Alert.alert("Error", "Could not remove photo. Please try again.");
    }
  };

  const { paddingBottom } = useTabScreenPadding();

  return (
    <SafeAreaView style={styles.container} accessibilityRole="none">
      <ScrollView contentContainerStyle={[styles.scrollContent, { paddingBottom }]}>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.title} accessibilityRole="header">StyleMate</Text>
            <Text style={styles.subtitle}>Your AI Wardrobe Assistant</Text>
          </View>
          <Avatar
            photoUrl={consentStatus?.photo_url}
            onPress={handleAvatarPress}
            size={40}
          />
          <TouchableOpacity
            style={styles.settingsBtn}
            onPress={() => router.push("/app/settings")}
            accessibilityLabel="Settings"
          >
            <Settings size={22} color={colors.accent} strokeWidth={1.5} />
          </TouchableOpacity>
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Wardrobe</Text>
          {Object.keys(wardrobeStats).length > 0 ? (
            <View style={styles.statsRow}>
              {Object.entries(wardrobeStats).map(([cat, count]) => (
                <View key={cat} style={styles.statItem}>
                  <Text style={styles.statCount}>{count}</Text>
                  <Text style={styles.statLabel}>{cat}</Text>
                </View>
              ))}
            </View>
          ) : (
            <Text style={styles.cardText}>
              Open the Wardrobe tab to start adding items.
            </Text>
          )}
          <TryOnUsageBadge />
        </View>

        {!checked ? (
          <ActivityIndicator style={{ marginTop: 20 }} color="#333" />
        ) : !seen ? (
          <TouchableOpacity
            style={styles.cta}
            onPress={() => router.push("/onboarding")}
          >
            <Text style={styles.ctaText}>Tell us your shape</Text>
          </TouchableOpacity>
        ) : null}

        {outfitLoading ? (
          <View style={styles.loadingSection}>
            <ActivityIndicator size="small" color="#333" />
          </View>
        ) : todaysOutfit ? (
          <>
            <View style={styles.divider} />
            <Text style={styles.sectionLabel}>Today's Outfit</Text>
            <TouchableOpacity
              style={styles.outfitCard}
              onPress={() => router.push("/(tabs)/outfit-suggestions")}
              activeOpacity={0.85}
            >
              <View style={styles.outfitThumbs}>
                {todaysOutfit.items.slice(0, 3).map((it) => (
                  <View key={it.id} style={styles.outfitThumb}>
                    {it.image_url ? (
                      <Image source={{ uri: resolvePhotoUrl(it.image_url, BASE_URL) ?? undefined }} style={styles.outfitThumbImg} />
                    ) : (
                      <View style={[styles.outfitThumbImg, styles.outfitThumbPlaceholder]}>
                        <Text style={styles.outfitThumbLetter}>{it.name?.[0] || "?"}</Text>
                      </View>
                    )}
                  </View>
                ))}
              </View>
              <View style={styles.outfitMeta}>
                <Text style={styles.outfitReason} numberOfLines={2}>{todaysOutfit.reason}</Text>
                <View style={styles.outfitScoreRow}>
                  <Star size={14} color={colors.warning} strokeWidth={1.5} fill={colors.warning} />
                  <Text style={styles.outfitScore}>{todaysOutfit.score.toFixed(2)}</Text>
                </View>
              </View>
            </TouchableOpacity>
          </>
        ) : null}

        {nextCalendarEntry && (
          <>
            <View style={styles.divider} />
            <Text style={styles.sectionLabel}>Upcoming</Text>
            <TouchableOpacity
              style={styles.linkButton}
              onPress={() => router.push("/(tabs)/calendar")}
            >
              <Text style={styles.linkButtonText}>
                {nextCalendarEntry.date}
                {nextCalendarEntry.occasion_tag ? ` · ${nextCalendarEntry.occasion_tag}` : ""}
                {nextCalendarEntry.locked_outfit_id != null ? " ✓" : ""}
              </Text>
            </TouchableOpacity>
          </>
        )}

        <View style={styles.divider} />

        <Text style={styles.sectionLabel}>My Photo</Text>

        {consentStatus?.photo_consent ? (
          <>
            {consentStatus?.photo_url && (
              <View style={styles.photoPreviewWrap}>
                <Image
                  source={{ uri: resolvePhotoUrl(consentStatus.photo_url, BASE_URL) ?? undefined }}
                  style={styles.photoPreview}
                  resizeMode="cover"
                />
              </View>
            )}
            <TouchableOpacity
              style={styles.linkButton}
              onPress={() => router.push("/capture")}
            >
              <Text style={styles.linkButtonText}>
                {consentStatus?.photo_url ? "Update my photo" : "Take my photo"}
              </Text>
            </TouchableOpacity>
            {consentStatus?.photo_url && (
              <TouchableOpacity
                style={[styles.linkButton, styles.deleteButton]}
                onPress={handleDeletePhoto}
              >
                <Text style={styles.deleteButtonText}>Delete my photo</Text>
              </TouchableOpacity>
            )}
          </>
        ) : (
          <TouchableOpacity
            style={[styles.linkButton, styles.linkButtonPrimary]}
            onPress={() => router.push("/consent")}
          >
            <Text style={styles.linkButtonTextPrimary}>Give photo consent first</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  scrollContent: { alignItems: "center", padding: spacing.xl },
  headerRow: { flexDirection: "row", alignItems: "flex-start", width: "100%", marginBottom: spacing.xxl - 4 },
  settingsBtn: { padding: spacing.sm, marginTop: spacing.xs },
  title: { fontSize: fontSize.xxxl, fontWeight: fontWeight.extrabold },
  subtitle: { fontSize: fontSize.base, color: "#666" },
  card: { backgroundColor: colors.surface, borderRadius: br.md, padding: spacing.xl, width: "100%", ...shadow.sm },
  cardTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.semibold, marginBottom: spacing.sm },
  cardText: { fontSize: fontSize.sm, color: "#555", lineHeight: 20 },
  statsRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.sm },
  statItem: { alignItems: "center", minWidth: 50 },
  statCount: { fontSize: fontSize.xl, fontWeight: fontWeight.bold, color: colors.accent },
  statLabel: { fontSize: fontSize.xs - 1, color: colors.text.light, textTransform: "capitalize" },
  loadingSection: { marginTop: spacing.xl, height: 40 },
  outfitCard: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.lg,
    ...shadow.sm,
  },
  outfitThumbs: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  outfitThumb: { flex: 1, borderRadius: br.sm, overflow: "hidden" },
  outfitThumbImg: { width: "100%", aspectRatio: 1, backgroundColor: "#e0e0e0" },
  outfitThumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  outfitThumbLetter: { fontSize: fontSize.xl, fontWeight: fontWeight.bold, color: colors.text.light },
  outfitMeta: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: spacing.sm },
  outfitReason: { flex: 1, fontSize: fontSize.xs, color: "#666", fontStyle: "italic" },
  outfitScoreRow: { flexDirection: "row", alignItems: "center", gap: spacing.xs - 1 },
  outfitScore: { fontSize: fontSize.sm, fontWeight: fontWeight.bold, color: colors.accent },
  cta: {
    marginTop: spacing.xl,
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.xxl,
    width: "100%",
    alignItems: "center",
  },
  ctaText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  divider: { height: 1, backgroundColor: "#ddd", width: "100%", marginVertical: spacing.xl },
  sectionLabel: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold, color: colors.text.light, textTransform: "uppercase", letterSpacing: 1, alignSelf: "flex-start", marginBottom: spacing.sm },
  photoPreviewWrap: {
    width: "100%",
    marginBottom: spacing.sm,
    borderRadius: br.md,
    overflow: "hidden",
    backgroundColor: "#e0e0e0",
  },
  photoPreview: {
    width: "100%",
    height: 200,
  },

  linkButton: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e0e0e0",
  },
  linkButtonPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  linkButtonText: { fontSize: fontSize.sm + 1, color: colors.accent, fontWeight: fontWeight.semibold },
  linkButtonTextPrimary: { fontSize: fontSize.sm + 1, color: colors.text.white, fontWeight: fontWeight.bold },
  deleteButton: { borderColor: "#c00" },
  deleteButtonText: { fontSize: fontSize.sm + 1, color: "#c00", fontWeight: fontWeight.semibold },
});
