import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Calendar, DateData } from "react-native-calendars";
import { router, useFocusEffect } from "expo-router";
import { manipulateAsync, SaveFormat } from "expo-image-manipulator";
import {
  CalendarEntry,
  calendarApi,
  outfitApi,
  OutfitSuggestion,
} from "../../lib/api";
import { BASE_URL } from "../../config/api";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../../theme/tokens";
import { Star } from "../../lib/icons";

const OCCASIONS = [
  "casual",
  "office",
  "ethnic",
  "party",
  "formal",
  "loungewear",
];

const CATEGORY_COLORS: Record<string, string> = {
  top: "#4A90D9",
  bottom: "#7B68EE",
  dress: "#E91E8A",
  outerwear: "#2ECC71",
  footwear: "#E8A317",
  accessory: "#E74C3C",
};

function getMonthBounds(year: number, month: number) {
  const start = `${year}-${String(month).padStart(2, "0")}-01`;
  const lastDay = new Date(year, month, 0).getDate();
  const end = `${year}-${String(month).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
  return { start_date: start, end_date: end };
}

function OutfitThumb({
  item,
}: {
  item: { id: number; name: string | null; category: string; image_url: string | null };
}) {
  const bg = CATEGORY_COLORS[item.category] || "#999";
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <View style={styles.outfitThumb}>
      {item.image_url && !imgFailed ? (
        <Image
          source={{ uri: `${BASE_URL}${item.image_url}` }}
          style={styles.outfitThumbImg}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <View
          style={[
            styles.outfitThumbImg,
            styles.outfitThumbPlaceholder,
            { backgroundColor: bg + "33" },
          ]}
        >
          <Text style={[styles.outfitThumbInitial, { color: bg }]}>
            {(item.name || item.category)?.[0]?.toUpperCase() || "?"}
          </Text>
        </View>
      )}
      <View style={[styles.outfitThumbBadge, { backgroundColor: bg }]}>
        <Text style={styles.outfitThumbBadgeText}>{item.category}</Text>
      </View>
    </View>
  );
}

export default function CalendarScreen() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);

  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [sheetVisible, setSheetVisible] = useState(false);
  const [activeEntry, setActiveEntry] = useState<CalendarEntry | null>(null);

  const [selectedOccasion, setSelectedOccasion] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<OutfitSuggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [lockingIndex, setLockingIndex] = useState<number | null>(null);
  const [viewerVisible, setViewerVisible] = useState(false);
  const [viewerImage, setViewerImage] = useState<string | null>(null);

  const loadEntries = useCallback(
    async (y?: number, m?: number) => {
      setLoading(true);
      try {
        const bounds = getMonthBounds(y ?? year, m ?? month);
        const data = await calendarApi.list(bounds);
        setEntries(data);
      } catch (e: any) {
        Alert.alert("Error", e.message);
      } finally {
        setLoading(false);
      }
    },
    [year, month]
  );

  useFocusEffect(
    useCallback(() => {
      loadEntries();
    }, [loadEntries])
  );

  const entryByDate = useMemo(() => {
    const map: Record<string, CalendarEntry> = {};
    for (const e of entries) map[e.date] = e;
    return map;
  }, [entries]);

  const markedDates = useMemo(() => {
    const marks: Record<string, any> = {};
    for (const e of entries) {
      marks[e.date] = {
        marked: true,
        dotColor: e.try_on_result_id != null
          ? "#9B59B6"
          : e.locked_outfit_id != null
            ? "#2ECC71"
            : "#E8A317",
      };
    }
    if (selectedDate && !marks[selectedDate]) {
      marks[selectedDate] = {};
    }
    if (selectedDate) {
      marks[selectedDate] = {
        ...marks[selectedDate],
        selected: true,
        selectedColor: "#333",
      };
    }
    return marks;
  }, [entries, selectedDate]);

  const loadSuggestions = async (occasion: string | null) => {
    setLoadingSuggestions(true);
    try {
      const data = await outfitApi.suggest({
        occasion_tag: occasion || undefined,
        limit: 5,
      });
      setSuggestions(data);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const openSheet = async (dateStr: string) => {
    setSelectedDate(dateStr);
    setSelectedOccasion(null);
    setSuggestions([]);

    let entry = entryByDate[dateStr];
    if (!entry) {
      try {
        entry = await calendarApi.create({ date: dateStr });
        setEntries((prev) => [...prev, entry!]);
      } catch (e: any) {
        Alert.alert("Error", e.message);
        return;
      }
    }
    setActiveEntry(entry);
    setSheetVisible(true);
    loadSuggestions(null);
  };

  const handleOccasionTap = (occ: string) => {
    const next = selectedOccasion === occ ? null : occ;
    setSelectedOccasion(next);
    loadSuggestions(next);
  };

  const handleLock = async (suggestion: OutfitSuggestion) => {
    if (!activeEntry) return;
    const outfitId = suggestion.items[0]?.id;
    if (!outfitId) return;
    setLockingIndex(outfitId);
    try {
      const updated = await calendarApi.update(activeEntry.id, {
        locked_outfit_id: outfitId,
      });
      setEntries((prev) =>
        prev.map((e) => (e.id === updated.id ? updated : e))
      );
      setActiveEntry(updated);
      setSheetVisible(false);
      setSelectedDate(null);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLockingIndex(null);
    }
  };

  const handleOpenTryOnViewer = () => {
    if (activeEntry?.try_on_result_image_url) {
      setViewerImage(`${BASE_URL}${activeEntry.try_on_result_image_url}`);
      setViewerVisible(true);
    }
  };

  const handleShareTryOn = async () => {
    if (!viewerImage) return;
    try {
      const Sharing = await import("expo-sharing");
      const result = await manipulateAsync(viewerImage, [], { format: SaveFormat.PNG });
      await Sharing.shareAsync(result.uri, {
        mimeType: "image/png",
        dialogTitle: "Share your try-on from StyleMate",
      });
    } catch {
      // share cancelled
    }
  };

  const handleRegenerateTryOn = () => {
    setViewerVisible(false);
    Alert.alert("Re-generate", "This would re-run the try-on. Redirecting to outfits.");
    router.push("/outfits");
  };

  const handleDayPress = (day: DateData) => {
    openSheet(day.dateString);
  };

  const handleMonthChange = (month: DateData) => {
    setYear(month.year);
    setMonth(month.month);
  };

  return (
    <SafeAreaView style={styles.container}>
      {loading ? (
        <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Loading calendar">
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Loading calendar...</Text>
        </View>
      ) : (
        <Calendar
          markedDates={markedDates}
          onDayPress={handleDayPress}
          onMonthChange={handleMonthChange}
          theme={{
            todayTextColor: "#333",
            arrowColor: "#333",
            textDayFontWeight: "500",
            textMonthFontWeight: "700",
            textDayHeaderFontWeight: "500",
          }}
        />
      )}

      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: "#E8A317" }]} />
          <Text style={styles.legendLabel}>Planned</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: "#2ECC71" }]} />
          <Text style={styles.legendLabel}>Locked</Text>
        </View>
      </View>

      {/* Bottom Sheet Modal */}
      <Modal
        visible={sheetVisible}
        animationType="slide"
        transparent
        onRequestClose={() => {
          setSheetVisible(false);
          setSelectedDate(null);
        }}
      >
        <TouchableOpacity
          style={styles.sheetOverlay}
          activeOpacity={1}
          onPress={() => {
            setSheetVisible(false);
            setSelectedDate(null);
          }}
        >
          <TouchableOpacity
            activeOpacity={1}
            style={styles.sheetContent}
            onPress={() => {}}
          >
            {/* Handle */}
            <View style={styles.sheetHandle} />

            {/* Header */}
            <View style={styles.sheetHeader}>
              <Text style={styles.sheetDate}>{selectedDate}</Text>
              {activeEntry?.locked_outfit_id != null && (
                <View style={styles.lockedBadge}>
                  <Text style={styles.lockedBadgeText}>Locked</Text>
                </View>
              )}
            </View>

            {/* Try-on result image */}
            {activeEntry?.try_on_result_image_url && (
              <View style={styles.tryOnImageContainer}>
                <Image
                  source={{ uri: `${BASE_URL}${activeEntry.try_on_result_image_url}` }}
                  style={styles.tryOnImage}
                  resizeMode="cover"
                />
                <View style={styles.tryOnImageOverlay} />
                {activeEntry?.occasion_tag && (
                  <View style={styles.tryOnOccasionChip}>
                    <Text style={styles.tryOnOccasionText}>{activeEntry.occasion_tag}</Text>
                  </View>
                )}
              </View>
            )}

            {/* Occasion chips */}
            <Text style={styles.sectionLabel}>Occasion</Text>
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.chipRow}
            >
              {OCCASIONS.map((occ) => {
                const active = selectedOccasion === occ;
                return (
                  <TouchableOpacity
                    key={occ}
                    style={[styles.chip, active && styles.chipActive]}
                    onPress={() => handleOccasionTap(occ)}
                  >
                    <Text
                      style={[
                        styles.chipText,
                        active && styles.chipTextActive,
                      ]}
                    >
                      {occ}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            {/* Outfit suggestions */}
            <Text style={styles.sectionLabel}>Outfit Suggestions</Text>
            {loadingSuggestions ? (
              <View style={styles.sheetCenter}>
                <ActivityIndicator size="small" color="#333" />
              </View>
            ) : suggestions.length === 0 ? (
              <View style={styles.sheetCenter}>
                <Text style={styles.emptyText}>
                  {selectedOccasion
                    ? `No outfits for "${selectedOccasion}"`
                    : "Select an occasion to see suggestions"}
                </Text>
              </View>
            ) : (
              <FlatList
                data={suggestions}
                keyExtractor={(_, i) => `sug-${i}`}
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.suggestionRow}
                renderItem={({ item: sug, index }) => {
                  const isLocked = activeEntry?.locked_outfit_id != null &&
                    sug.items.some((it) => it.id === activeEntry!.locked_outfit_id);
                  const isLocking = lockingIndex != null && sug.items.some((it) => it.id === lockingIndex);
                  return (
                    <View
                      style={[
                        styles.suggestionCard,
                        isLocked && styles.suggestionCardLocked,
                      ]}
                    >
                      <View style={styles.suggestionThumbs}>
                        {sug.items.map((it) => (
                          <OutfitThumb key={it.id} item={it} />
                        ))}
                      </View>
                      <Text style={styles.suggestionReason} numberOfLines={2}>
                        {sug.reason}
                      </Text>
                      <View style={styles.suggestionFooter}>
                        <View style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
                          <Star size={14} color="#E8A317" strokeWidth={1.5} fill="#E8A317" />
                          <Text style={styles.suggestionScore}>
                            {sug.score.toFixed(2)}
                          </Text>
                        </View>
                      </View>
                      <TouchableOpacity
                        style={[
                          styles.lockBtn,
                          isLocked && styles.lockBtnDone,
                        ]}
                        onPress={() => handleLock(sug)}
                        disabled={isLocking || isLocked}
                      >
                        <Text
                          style={[
                            styles.lockBtnText,
                            (isLocked || isLocking) && styles.lockBtnTextDone,
                          ]}
                        >
                          {isLocked
                            ? "Locked"
                            : isLocking
                              ? "Locking..."
                              : "Lock this outfit"}
                        </Text>
                      </TouchableOpacity>
                    </View>
                  );
                }}
              />
            )}
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* Try-on full-screen viewer */}
      <Modal visible={viewerVisible} animationType="fade" onRequestClose={() => setViewerVisible(false)}>
        <SafeAreaView style={styles.viewerContainer}>
          {viewerImage && (
            <Image source={{ uri: viewerImage }} style={styles.viewerImage} resizeMode="contain" />
          )}
          <View style={styles.viewerActions}>
            <TouchableOpacity style={styles.viewerBtn} onPress={handleShareTryOn} accessibilityLabel="Share try-on">
              <Text style={styles.viewerBtnText}>Share</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.viewerBtn} onPress={handleRegenerateTryOn} accessibilityLabel="Re-generate try-on">
              <Text style={styles.viewerBtnText}>Re-generate</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[styles.viewerBtn, styles.viewerClose]} onPress={() => setViewerVisible(false)} accessibilityLabel="Close viewer">
              <Text style={styles.viewerCloseText}>Close</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm },

  // Legend
  legend: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.xl,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: spacing.xs + 2 },
  legendDot: { width: 8, height: 8, borderRadius: spacing.xs },
  legendLabel: { fontSize: fontSize.xs, color: colors.text.tertiary },

  // Sheet overlay
  sheetOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  sheetContent: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: spacing.xl - 4,
    borderTopRightRadius: spacing.xl - 4,
    maxHeight: "80%",
    paddingBottom: spacing.xxl - 2,
  },
  sheetHandle: {
    width: 36,
    height: 4,
    borderRadius: spacing.xs - 2,
    backgroundColor: "#ddd",
    alignSelf: "center",
    marginTop: spacing.sm + 2,
    marginBottom: spacing.sm + 6,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm + 6,
  },
  sheetDate: { fontSize: fontSize.lg, fontWeight: fontWeight.bold, color: colors.accent },
  lockedBadge: {
    backgroundColor: colors.success + "22",
    borderRadius: br.sm,
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.xs,
  },
  lockedBadgeText: { color: colors.success, fontSize: fontSize.xs, fontWeight: fontWeight.semibold },

  // Section
  sectionLabel: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.semibold,
    color: colors.text.tertiary,
    paddingHorizontal: spacing.xl,
    marginBottom: spacing.sm,
    marginTop: spacing.xs + 2,
  },

  // Chips
  chipRow: { paddingHorizontal: spacing.lg, paddingBottom: spacing.md, gap: spacing.sm },
  chip: {
    paddingHorizontal: spacing.sm + 6,
    paddingVertical: spacing.xs + 3,
    borderRadius: 20,
    backgroundColor: "#e8e8e8",
  },
  chipActive: { backgroundColor: colors.accent },
  chipText: { fontSize: fontSize.xs + 1, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: colors.text.white },

  // Suggestions
  suggestionRow: { paddingHorizontal: spacing.lg, gap: spacing.md },
  sheetCenter: { height: 80, alignItems: "center", justifyContent: "center" },
  emptyText: { fontSize: fontSize.sm, color: colors.text.tertiary },

  // Suggestion card
  suggestionCard: {
    width: 200,
    backgroundColor: "#f9f9f9",
    borderRadius: br.md,
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "transparent",
  },
  suggestionCardLocked: { borderColor: colors.success, backgroundColor: "#f0faf4" },
  suggestionThumbs: { flexDirection: "row", padding: spacing.sm, gap: spacing.xs + 2 },
  suggestionReason: {
    fontSize: fontSize.xs,
    color: "#666",
    fontStyle: "italic",
    paddingHorizontal: spacing.sm + 2,
    marginBottom: spacing.xs,
  },
  suggestionFooter: {
    paddingHorizontal: spacing.sm + 2,
    paddingBottom: spacing.sm,
  },
  suggestionScore: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold, color: colors.accent },

  // Lock button
  lockBtn: {
    backgroundColor: colors.accent,
    paddingVertical: spacing.sm + 2,
    alignItems: "center",
  },
  lockBtnDone: { backgroundColor: "#e0e0e0" },
  lockBtnText: { color: colors.text.white, fontSize: fontSize.xs + 1, fontWeight: fontWeight.semibold },
  lockBtnTextDone: { color: colors.text.tertiary },

  // Outfit thumb (inside sheet)
  outfitThumb: { position: "relative", borderRadius: br.sm, overflow: "hidden" },
  outfitThumbImg: {
    width: 50,
    height: 50,
    borderRadius: br.sm,
    backgroundColor: "#e0e0e0",
  },
  outfitThumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  outfitThumbInitial: { fontSize: fontSize.base, fontWeight: fontWeight.bold },
  outfitThumbBadge: {
    position: "absolute",
    bottom: 2,
    left: 2,
    borderRadius: spacing.xs - 1,
    paddingHorizontal: spacing.xs,
    paddingVertical: 1,
  },
  outfitThumbBadgeText: {
    color: colors.text.white,
    fontSize: 7,
    fontWeight: fontWeight.bold,
    textTransform: "uppercase",
  },

  tryOnImageContainer: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    borderRadius: br.md + 4,
    overflow: "hidden",
    position: "relative",
    backgroundColor: "#e0e0e0",
  },
  tryOnImage: {
    width: "100%",
    height: 220,
    borderRadius: br.md + 4,
  },
  tryOnImageOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    height: 60,
    backgroundColor: "rgba(0,0,0,0.25)",
  },
  tryOnOccasionChip: {
    position: "absolute",
    bottom: spacing.sm,
    left: spacing.md,
    backgroundColor: "rgba(0,0,0,0.5)",
    borderRadius: 12,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  tryOnOccasionText: {
    color: "#fff",
    fontSize: fontSize.xs,
    fontWeight: fontWeight.semibold,
  },

  viewerContainer: {
    flex: 1,
    backgroundColor: "#000",
    alignItems: "center",
    justifyContent: "center",
  },
  viewerImage: {
    width: "100%",
    height: "70%",
  },
  viewerActions: {
    flexDirection: "row",
    gap: spacing.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
    width: "100%",
    justifyContent: "center",
  },
  viewerBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.xl,
    alignItems: "center",
    minWidth: 120,
  },
  viewerBtnText: {
    color: colors.text.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
  },
  viewerClose: {
    backgroundColor: "#555",
  },
  viewerCloseText: {
    color: colors.text.white,
    fontSize: fontSize.base,
    fontWeight: fontWeight.bold,
  },
});
