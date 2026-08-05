import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";

import { Check, Gem, RefreshCw } from "../lib/icons";
import { CapsuleItem, CapsuleResponse, outfitApi } from "../lib/api";
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

const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
// Slider is a stepped row of buttons — the plan's 10-40 range in the sizes
// people actually pick, without pulling in a slider dependency.
const TARGET_COUNTS = [10, 15, 20, 25, 30, 40];

export default function CapsuleScreen() {
  const navigation = useNavigation();
  const [targetCount, setTargetCount] = useState(10);
  const [occasion, setOccasion] = useState<string | null>(null);
  const [locked, setLocked] = useState<number[]>([]);
  const [capsule, setCapsule] = useState<CapsuleResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleBack = useCallback(() => {
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      router.replace("/(tabs)");
    }
    return true;
  }, [navigation]);

  useHardwareBack(handleBack);

  const build = useCallback(
    async (lockedIds: number[] = locked) => {
      setLoading(true);
      setError(null);
      try {
        setCapsule(
          await outfitApi.buildCapsule({
            target_item_count: targetCount,
            occasion_tag: occasion,
            locked_item_ids: lockedIds,
          }),
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [targetCount, occasion, locked],
  );

  useEffect(() => {
    build();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetCount, occasion]);

  const toggleLock = (itemId: number) => {
    const next = locked.includes(itemId)
      ? locked.filter((id) => id !== itemId)
      : [...locked, itemId];
    setLocked(next);
    build(next);
  };

  const byCategory = (capsule?.items ?? []).reduce<Record<string, CapsuleItem[]>>(
    (acc, item) => {
      const cat = item.category || "other";
      (acc[cat] ||= []).push(item);
      return acc;
    },
    {},
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <BackButton title="Capsule Wardrobe" />
        <TouchableOpacity onPress={() => build()} accessibilityLabel="Regenerate capsule">
          <RefreshCw size={20} color={colors.accent} strokeWidth={1.5} />
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.label}>Target size</Text>
        <View style={styles.chipRow}>
          {TARGET_COUNTS.map((n) => (
            <TouchableOpacity
              key={n}
              style={[styles.chip, targetCount === n && styles.chipActive]}
              onPress={() => setTargetCount(n)}
            >
              <Text style={[styles.chipText, targetCount === n && styles.chipTextActive]}>
                {n}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Occasion</Text>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={OCCASIONS}
          keyExtractor={(o) => o}
          contentContainerStyle={styles.chipRow}
          renderItem={({ item: o }) => (
            <TouchableOpacity
              style={[styles.chip, occasion === o && styles.chipActive]}
              onPress={() => setOccasion(occasion === o ? null : o)}
            >
              <Text style={[styles.chipText, occasion === o && styles.chipTextActive]}>{o}</Text>
            </TouchableOpacity>
          )}
        />

        {loading ? (
          <View style={styles.loadingBox} accessibilityRole="progressbar">
            <ActivityIndicator color={colors.accent} />
            <Text style={styles.loadingText}>Scoring every pair...</Text>
          </View>
        ) : error ? (
          <Text style={styles.errorText}>{error}</Text>
        ) : capsule ? (
          <>
            <View style={styles.statsCard}>
              <View style={styles.statsHeadline}>
                <Gem size={20} color={colors.accent} strokeWidth={1.5} />
                <Text style={styles.statsBig}>
                  {capsule.items.length} items → {capsule.total_outfits} outfits
                </Text>
              </View>
              <Text style={styles.statsMeta}>
                {capsule.pair_count} strong pairs · picked from {capsule.wardrobe_size} in your wardrobe
              </Text>
              <View style={styles.statsCats}>
                {Object.entries(capsule.categories).map(([cat, count]) => (
                  <Text key={cat} style={styles.statsCat}>
                    {count} {cat}
                  </Text>
                ))}
              </View>
            </View>

            {capsule.items.length === 0 && (
              <Text style={styles.errorText}>
                No items match that occasion yet — try clearing the filter.
              </Text>
            )}

            {Object.entries(byCategory).map(([cat, items]) => (
              <View key={cat}>
                <Text style={styles.sectionLabel}>{cat}</Text>
                <View style={styles.grid}>
                  {items.map((item) => {
                    const isLocked = locked.includes(item.id);
                    return (
                      <TouchableOpacity
                        key={item.id}
                        style={[styles.itemCard, isLocked && styles.itemCardLocked]}
                        onPress={() => toggleLock(item.id)}
                        activeOpacity={0.85}
                      >
                        {item.image_url ? (
                          <Image
                            source={{ uri: resolvePhotoUrl(item.image_url, BASE_URL) ?? undefined }}
                            style={styles.itemImage}
                          />
                        ) : (
                          <View style={[styles.itemImage, styles.itemPlaceholder]}>
                            <Text style={styles.itemLetter}>{item.name?.[0] || "?"}</Text>
                          </View>
                        )}
                        {isLocked && (
                          <View style={styles.lockBadge}>
                            <Check size={12} color={colors.text.white} strokeWidth={2} />
                          </View>
                        )}
                        <Text style={styles.itemName} numberOfLines={1}>
                          {item.name || item.category}
                        </Text>
                        <Text style={styles.itemMeta}>{item.outfit_count} good pairs</Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            ))}

            <Text style={styles.hint}>Tap an item to lock it into the capsule.</Text>
          </>
        ) : null}
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
  title: { flex: 1, fontSize: fontSize.xl, fontWeight: fontWeight.bold },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl, width: "100%", maxWidth: 760, alignSelf: "center" },
  label: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: br.full,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { fontSize: fontSize.sm, color: colors.accent, textTransform: "capitalize" },
  chipTextActive: { color: colors.text.white, fontWeight: fontWeight.semibold },
  loadingBox: { alignItems: "center", gap: spacing.sm, marginTop: spacing.xxl },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary },
  errorText: { marginTop: spacing.xl, fontSize: fontSize.sm, color: colors.text.secondary },
  statsCard: {
    marginTop: spacing.xl,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.lg,
    ...shadow.sm,
  },
  statsHeadline: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  statsBig: { fontSize: fontSize.lg, fontWeight: fontWeight.bold, color: colors.accent },
  statsMeta: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },
  statsCats: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginTop: spacing.sm },
  statsCat: { fontSize: fontSize.xs, color: colors.text.light, textTransform: "capitalize" },
  sectionLabel: {
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  itemCard: {
    width: "31%",
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.xs,
    borderWidth: 2,
    borderColor: "transparent",
  },
  itemCardLocked: { borderColor: colors.success },
  itemImage: { width: "100%", aspectRatio: 1, borderRadius: br.sm, backgroundColor: "#e0e0e0" },
  itemPlaceholder: { alignItems: "center", justifyContent: "center" },
  itemLetter: { fontSize: fontSize.xl, fontWeight: fontWeight.bold, color: colors.text.light },
  lockBadge: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    backgroundColor: colors.success,
    borderRadius: br.full,
    padding: 3,
  },
  itemName: { fontSize: fontSize.xs, color: colors.accent, marginTop: spacing.xs },
  itemMeta: { fontSize: fontSize.xs - 2, color: colors.text.light },
  hint: { marginTop: spacing.xl, fontSize: fontSize.xs, color: colors.text.light, textAlign: "center" },
});
