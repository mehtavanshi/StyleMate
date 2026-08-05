import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Linking,
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
import {
  ChevronRight,
  CloudSun,
  Gem,
  Luggage,
  Settings,
  ShoppingBag,
  Sparkles,
  Star,
} from "../../lib/icons";

import {
  CalendarEntry,
  calendarApi,
  ClosetGap,
  clothingApi,
  ConsentStatus,
  DEMO_USER_ID,
  consentApi,
  outfitApi,
  OutfitSuggestion,
  shoppingApi,
  WeatherOutfitResponse,
} from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";
import TryOnUsageBadge from "../../components/TryOnUsageBadge";
import Avatar from "../../components/Avatar";
import { useTabScreenPadding } from "../../lib/useTabScreenPadding";

const ONBOARDING_FLAG = "onboarding_complete";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Hand-rolled instead of toLocaleDateString — Intl is not guaranteed on Hermes.
const formatDay = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`);
  if (isNaN(d.getTime())) return iso;
  return `${WEEKDAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]}`;
};

export default function HomeScreen() {
  const [checked, setChecked] = useState(false);
  const [seen, setSeen] = useState(false);
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [todaysOutfit, setTodaysOutfit] = useState<OutfitSuggestion | null>(null);
  const [outfitLoading, setOutfitLoading] = useState(true);
  const [wardrobeStats, setWardrobeStats] = useState<Record<string, number>>({});
  const [nextCalendarEntry, setNextCalendarEntry] = useState<CalendarEntry | null>(null);
  const [gaps, setGaps] = useState<ClosetGap[] | null>(null);
  const [weather, setWeather] = useState<WeatherOutfitResponse | null>(null);

  const loadHomeData = useCallback(async () => {
    setOutfitLoading(true);
    try {
      const [suggestions, items, entries] = await Promise.all([
        outfitApi.suggest({ limit: 1 }),
        clothingApi.list(),
        calendarApi.list({ start_date: new Date().toISOString().split("T")[0] }),
      ]);
      // /outfit-suggestions returns { outfits, total } — the old code read
      // .length off the envelope, so Today's Outfit never rendered.
      if (suggestions.outfits?.length) setTodaysOutfit(suggestions.outfits[0]);
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

  // Gaps and weather load on their own so a slow or unconfigured one never
  // holds up (or wipes out) the rest of the home screen.
  const loadExtras = useCallback(async () => {
    shoppingApi
      .gaps()
      .then(setGaps)
      .catch(() => setGaps([]));
    outfitApi
      .weatherSuggest()
      .then(setWeather)
      .catch(() => setWeather(null));
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
    loadExtras();
  }, [loadHomeData, loadExtras]);

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

  // Settings is the profile screen: it manages the same photo (upload,
  // replace, delete) on a routed screen with a back button, instead of an
  // Alert action sheet the user can't navigate back from.
  const handleAvatarPress = () => router.push("/settings");

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
            onPress={() => router.push("/settings")}
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

        {weather?.weather && (
          <View style={styles.weatherCard}>
            <View style={styles.weatherHeader}>
              <CloudSun size={22} color={colors.accent} strokeWidth={1.5} />
              <Text style={styles.weatherTemp}>
                {Math.round(weather.weather.temp_c)}°C
              </Text>
              <Text style={styles.weatherMeta}>
                {weather.weather.condition} · {weather.weather.city}
              </Text>
            </View>
            {weather.guidance && (
              <Text style={styles.weatherGuidance}>
                {weather.guidance.season} picks · {weather.guidance.fabrics.slice(0, 3).join(", ")}
              </Text>
            )}
            {weather.outfit ? (
              <TouchableOpacity
                style={styles.weatherPick}
                onPress={() => router.push("/(tabs)/outfit-suggestions")}
                activeOpacity={0.85}
              >
                <View style={styles.weatherThumbs}>
                  {weather.outfit.items.slice(0, 3).map((it) => (
                    <View key={it.id} style={styles.weatherThumb}>
                      {it.image_url ? (
                        <Image
                          source={{ uri: resolvePhotoUrl(it.image_url, BASE_URL) ?? undefined }}
                          style={styles.weatherThumbImg}
                        />
                      ) : (
                        <View style={[styles.weatherThumbImg, styles.outfitThumbPlaceholder]}>
                          <Text style={styles.outfitThumbLetter}>{it.name?.[0] || "?"}</Text>
                        </View>
                      )}
                    </View>
                  ))}
                </View>
                <Text style={styles.weatherPickLabel}>Today's weather pick</Text>
              </TouchableOpacity>
            ) : (
              <Text style={styles.cardText}>{weather.message}</Text>
            )}
          </View>
        )}

        {gaps !== null && gaps.length > 0 && (
          <>
            <View style={styles.divider} />
            <Text style={styles.sectionLabel}>Closet Gaps</Text>
            <FlatList
              horizontal
              showsHorizontalScrollIndicator={false}
              data={gaps}
              keyExtractor={(g, i) => `${g.missing_category}-${i}`}
              contentContainerStyle={styles.gapRow}
              style={{ width: "100%" }}
              renderItem={({ item: gap }) => (
                <TouchableOpacity
                  style={styles.gapCard}
                  activeOpacity={0.85}
                  onPress={() => {
                    const link = gap.shopping_links[0];
                    if (link) Linking.openURL(link.url);
                  }}
                >
                  <View style={styles.gapCardHeader}>
                    <ShoppingBag size={16} color={colors.accent} strokeWidth={1.5} />
                    <Text style={styles.gapCategory}>{gap.missing_category}</Text>
                  </View>
                  <Text style={styles.gapReason} numberOfLines={3}>{gap.reason}</Text>
                  <Text style={styles.gapQuery}>Shop “{gap.search_query}”</Text>
                </TouchableOpacity>
              )}
            />
          </>
        )}

        {gaps !== null && gaps.length === 0 && (
          <>
            <View style={styles.divider} />
            <Text style={styles.sectionLabel}>Closet Gaps</Text>
            <Text style={styles.cardText}>Your wardrobe looks well-rounded!</Text>
          </>
        )}

        <View style={styles.divider} />
        <Text style={styles.sectionLabel}>AI Tools</Text>
        {[
          { label: "Rate my style", route: "/style-rating", Icon: Sparkles },
          { label: "Capsule wardrobe", route: "/capsule", Icon: Gem },
          { label: "Packing assistant", route: "/packing", Icon: Luggage },
        ].map(({ label, route, Icon }) => (
          <TouchableOpacity
            key={route}
            style={styles.toolRow}
            onPress={() => router.push(route as any)}
          >
            <Icon size={18} color={colors.accent} strokeWidth={1.5} />
            <Text style={styles.toolLabel}>{label}</Text>
            <ChevronRight size={18} color={colors.text.light} strokeWidth={1.5} />
          </TouchableOpacity>
        ))}

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
              style={styles.outfitCard}
              onPress={() => router.push("/(tabs)/calendar")}
              activeOpacity={0.85}
            >
              {/* ponytail: try-on render first, otherwise the outfit's own
                  item images. A single merged top+bottom+shoes image needs the
                  full-outfit try-on model from third_new_feature.md — not built
                  yet, but the date no longer renders as a bare number. */}
              {nextCalendarEntry.try_on_result_image_url ? (
                <Image
                  source={{
                    uri:
                      resolvePhotoUrl(nextCalendarEntry.try_on_result_image_url, BASE_URL) ??
                      undefined,
                  }}
                  style={styles.upcomingImage}
                  resizeMode="cover"
                />
              ) : nextCalendarEntry.locked_outfit_items?.length ? (
                <View style={styles.outfitThumbs}>
                  {nextCalendarEntry.locked_outfit_items.slice(0, 4).map((it) => (
                    <View key={it.id} style={styles.outfitThumb}>
                      {it.image_url ? (
                        <Image
                          source={{ uri: resolvePhotoUrl(it.image_url, BASE_URL) ?? undefined }}
                          style={styles.outfitThumbImg}
                        />
                      ) : (
                        <View style={[styles.outfitThumbImg, styles.outfitThumbPlaceholder]}>
                          <Text style={styles.outfitThumbLetter}>
                            {(it.name || it.category)?.[0]?.toUpperCase() || "?"}
                          </Text>
                        </View>
                      )}
                    </View>
                  ))}
                </View>
              ) : (
                <View style={[styles.upcomingImage, styles.outfitThumbPlaceholder]}>
                  <Text style={styles.upcomingEmpty}>No outfit picked yet</Text>
                </View>
              )}
              <View style={styles.outfitMeta}>
                <Text style={styles.upcomingDate}>{formatDay(nextCalendarEntry.date)}</Text>
                {nextCalendarEntry.occasion_tag ? (
                  <Text style={styles.upcomingTag}>{nextCalendarEntry.occasion_tag}</Text>
                ) : null}
                {nextCalendarEntry.locked_outfit_id != null && (
                  <Text style={styles.upcomingLocked}>locked</Text>
                )}
              </View>
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
  scrollContent: { alignItems: "center", padding: spacing.xl, width: "100%", maxWidth: 760, alignSelf: "center" },
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

  // Weather widget (4.4)
  weatherCard: {
    width: "100%",
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.lg,
    ...shadow.sm,
  },
  weatherHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  weatherTemp: { fontSize: fontSize.xxl, fontWeight: fontWeight.bold, color: colors.accent },
  weatherMeta: { flex: 1, fontSize: fontSize.xs, color: colors.text.secondary, textTransform: "capitalize" },
  weatherGuidance: { fontSize: fontSize.xs, color: colors.text.light, marginTop: spacing.xs },
  weatherPick: { marginTop: spacing.md },
  weatherThumbs: { flexDirection: "row", gap: spacing.sm },
  weatherThumb: { flex: 1, borderRadius: br.sm, overflow: "hidden" },
  weatherThumbImg: { width: "100%", aspectRatio: 1, backgroundColor: "#e0e0e0" },
  weatherPickLabel: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },

  // Closet gaps (4.1)
  gapRow: { gap: spacing.sm, paddingRight: spacing.lg },
  gapCard: {
    width: 190,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  gapCardHeader: { flexDirection: "row", alignItems: "center", gap: spacing.xs, marginBottom: spacing.xs },
  gapCategory: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, textTransform: "capitalize" },
  gapReason: { fontSize: fontSize.xs, color: colors.text.secondary, lineHeight: 16 },
  gapQuery: { fontSize: fontSize.xs, color: colors.accent, fontWeight: fontWeight.semibold, marginTop: spacing.sm },

  // AI tool links (4.5 / 4.6 / 4.7 entry points)
  toolRow: {
    width: "100%",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  toolLabel: { flex: 1, fontSize: fontSize.sm + 1, color: colors.accent, fontWeight: fontWeight.semibold },

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
  upcomingImage: {
    width: "100%",
    height: 160,
    borderRadius: br.sm,
    backgroundColor: "#e0e0e0",
    marginBottom: spacing.sm,
  },
  upcomingDate: { flex: 1, fontSize: fontSize.base, fontWeight: fontWeight.bold, color: colors.text.primary },
  upcomingTag: {
    fontSize: fontSize.xs,
    color: colors.accent,
    backgroundColor: colors.background,
    borderRadius: br.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs - 1,
    textTransform: "capitalize",
  },
  upcomingLocked: { fontSize: fontSize.xs, color: colors.success, fontWeight: fontWeight.semibold },
  upcomingEmpty: { fontSize: fontSize.sm, color: colors.text.light },
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
