import { useCallback, useState } from "react";
import {
  ActivityIndicator,
  Image,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";

import { Check, Lightbulb, Luggage, ShoppingBag } from "../lib/icons";
import { packingApi, PackingList } from "../lib/api";
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

const PURPOSES = ["leisure", "business", "beach", "wedding", "adventure"];
const DURATIONS = [2, 3, 4, 5, 7, 10, 14];

export default function PackingScreen() {
  const navigation = useNavigation();
  const [destination, setDestination] = useState("");
  const [duration, setDuration] = useState(4);
  const [purpose, setPurpose] = useState("leisure");
  const [list, setList] = useState<PackingList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [packed, setPacked] = useState<number[]>([]);

  const handleBack = useCallback(() => {
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      router.replace("/(tabs)");
    }
    return true;
  }, [navigation]);

  useHardwareBack(handleBack);

  const generate = async () => {
    if (!destination.trim()) {
      setError("Where are you going?");
      return;
    }
    setLoading(true);
    setError(null);
    setPacked([]);
    try {
      setList(await packingApi.generate(destination.trim(), duration, purpose));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const togglePacked = (id: number) =>
    setPacked((prev) => (prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]));

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <BackButton title="Packing Assistant" />
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.label}>Destination</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Goa"
          placeholderTextColor={colors.text.muted}
          value={destination}
          onChangeText={setDestination}
          onSubmitEditing={generate}
          returnKeyType="go"
        />

        <Text style={styles.label}>Days</Text>
        <View style={styles.chipRow}>
          {DURATIONS.map((d) => (
            <TouchableOpacity
              key={d}
              style={[styles.chip, duration === d && styles.chipActive]}
              onPress={() => setDuration(d)}
            >
              <Text style={[styles.chipText, duration === d && styles.chipTextActive]}>{d}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <Text style={styles.label}>Purpose</Text>
        <View style={styles.chipRow}>
          {PURPOSES.map((p) => (
            <TouchableOpacity
              key={p}
              style={[styles.chip, purpose === p && styles.chipActive]}
              onPress={() => setPurpose(p)}
            >
              <Text style={[styles.chipText, purpose === p && styles.chipTextActive]}>{p}</Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={[styles.primaryBtn, loading && styles.primaryBtnDisabled]}
          onPress={generate}
          disabled={loading}
        >
          <View style={styles.btnInner}>
            <Luggage size={16} color={colors.text.white} strokeWidth={1.5} />
            <Text style={styles.primaryBtnText}>{loading ? "Packing..." : "Generate list"}</Text>
          </View>
        </TouchableOpacity>

        {loading && (
          <View style={styles.loadingBox} accessibilityRole="progressbar">
            <ActivityIndicator color={colors.accent} />
          </View>
        )}

        {error && <Text style={styles.errorText}>{error}</Text>}

        {list && (
          <>
            {!!list.weather_note && <Text style={styles.weatherNote}>{list.weather_note}</Text>}

            <Text style={styles.sectionLabel}>
              From Your Wardrobe ({packed.length}/{list.selected_items.length})
            </Text>
            {list.selected_items.length === 0 ? (
              <Text style={styles.emptyText}>
                Nothing in your wardrobe matches this trip yet.
              </Text>
            ) : (
              list.selected_items.map((item) => {
                const isPacked = packed.includes(item.id);
                return (
                  <TouchableOpacity
                    key={item.id}
                    style={styles.packRow}
                    onPress={() => togglePacked(item.id)}
                    activeOpacity={0.85}
                  >
                    <View style={[styles.checkbox, isPacked && styles.checkboxOn]}>
                      {isPacked && <Check size={14} color={colors.text.white} strokeWidth={2.5} />}
                    </View>
                    {item.image_url ? (
                      <Image
                        source={{ uri: resolvePhotoUrl(item.image_url, BASE_URL) ?? undefined }}
                        style={styles.packThumb}
                      />
                    ) : (
                      <View style={[styles.packThumb, styles.packThumbEmpty]} />
                    )}
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.packName, isPacked && styles.packNameDone]}>
                        {item.name || item.category}
                      </Text>
                      <Text style={styles.packMeta}>
                        {item.category}
                        {item.note ? ` · ${item.note}` : ""}
                      </Text>
                    </View>
                  </TouchableOpacity>
                );
              })
            )}

            {list.missing_groups.length > 0 && (
              <>
                <Text style={styles.sectionLabel}>Items to Buy</Text>
                {list.missing_groups.map((group) => (
                  <View key={group.category} style={styles.buyCard}>
                    <View style={styles.buyHeader}>
                      <ShoppingBag size={16} color={colors.accent} strokeWidth={1.5} />
                      <Text style={styles.buyTitle}>
                        {group.quantity_needed} × {group.category}
                      </Text>
                    </View>
                    {!!group.note && <Text style={styles.buyNote}>{group.note}</Text>}
                    <View style={styles.storeRow}>
                      {group.shopping_links.slice(0, 3).map((link) => (
                        <TouchableOpacity
                          key={link.store}
                          style={styles.storeBtn}
                          onPress={() => Linking.openURL(link.url)}
                        >
                          <Text style={styles.storeBtnText}>{link.store}</Text>
                        </TouchableOpacity>
                      ))}
                    </View>
                  </View>
                ))}
              </>
            )}

            {list.tips.length > 0 && (
              <>
                <Text style={styles.sectionLabel}>Tips</Text>
                {list.tips.map((tip, i) => (
                  <View key={i} style={styles.tipRow}>
                    <Lightbulb size={14} color={colors.warning} strokeWidth={1.5} />
                    <Text style={styles.tipText}>{tip}</Text>
                  </View>
                ))}
              </>
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
  label: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: br.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    fontSize: fontSize.base,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text.primary,
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
  primaryBtn: {
    marginTop: spacing.xl,
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.md + 2,
    alignItems: "center",
  },
  primaryBtnDisabled: { opacity: 0.6 },
  primaryBtnText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  btnInner: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  loadingBox: { alignItems: "center", marginTop: spacing.lg },
  errorText: { marginTop: spacing.lg, fontSize: fontSize.sm, color: colors.danger },
  emptyText: { fontSize: fontSize.sm, color: colors.text.secondary },
  weatherNote: {
    marginTop: spacing.xl,
    fontSize: fontSize.sm,
    color: colors.text.secondary,
    fontStyle: "italic",
  },
  sectionLabel: {
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  packRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: br.sm,
    borderWidth: 2,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxOn: { backgroundColor: colors.success, borderColor: colors.success },
  packThumb: { width: 44, height: 44, borderRadius: br.sm, backgroundColor: "#e0e0e0" },
  packThumbEmpty: { backgroundColor: "#e6e6e6" },
  packName: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.accent },
  packNameDone: { textDecorationLine: "line-through", color: colors.text.light },
  packMeta: { fontSize: fontSize.xs, color: colors.text.light, textTransform: "capitalize" },
  buyCard: {
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    ...shadow.sm,
  },
  buyHeader: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  buyTitle: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, textTransform: "capitalize" },
  buyNote: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },
  storeRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.sm },
  storeBtn: {
    backgroundColor: colors.background,
    borderRadius: br.full,
    paddingVertical: spacing.xs + 2,
    paddingHorizontal: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  storeBtnText: { fontSize: fontSize.xs, color: colors.accent, textTransform: "capitalize" },
  tipRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing.sm, marginBottom: spacing.sm },
  tipText: { flex: 1, fontSize: fontSize.sm, color: colors.text.secondary, lineHeight: 19 },
});
