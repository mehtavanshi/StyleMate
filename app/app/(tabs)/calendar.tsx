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
import { Calendar, DateData } from "react-native-calendars";
import { useFocusEffect } from "expo-router";
import {
  CalendarEntry,
  calendarApi,
  outfitApi,
  OutfitSuggestion,
} from "../../lib/api";
import { BASE_URL } from "../../config/api";

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
        dotColor: e.locked_outfit_id != null ? "#2ECC71" : "#E8A317",
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

  const handleLock = async (suggestionIndex: number) => {
    if (!activeEntry) return;
    setLockingIndex(suggestionIndex);
    try {
      const updated = await calendarApi.update(activeEntry.id, {
        locked_outfit_id: suggestionIndex,
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

  const handleDayPress = (day: DateData) => {
    openSheet(day.dateString);
  };

  const handleMonthChange = (month: DateData) => {
    setYear(month.year);
    setMonth(month.month);
  };

  return (
    <View style={styles.container}>
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
                  const isLocked = activeEntry?.locked_outfit_id === index;
                  const isLocking = lockingIndex === index;
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
                        <Text style={styles.suggestionScore}>
                          ★ {sug.score.toFixed(2)}
                        </Text>
                      </View>
                      <TouchableOpacity
                        style={[
                          styles.lockBtn,
                          isLocked && styles.lockBtnDone,
                        ]}
                        onPress={() => handleLock(index)}
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
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { fontSize: 14, color: "#888", marginTop: 10 },

  // Legend
  legend: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 20,
    paddingVertical: 12,
    backgroundColor: "#fff",
    borderTopWidth: 1,
    borderTopColor: "#eee",
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendLabel: { fontSize: 12, color: "#888" },

  // Sheet overlay
  sheetOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "flex-end",
  },
  sheetContent: {
    backgroundColor: "#fff",
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: "80%",
    paddingBottom: 30,
  },
  sheetHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#ddd",
    alignSelf: "center",
    marginTop: 10,
    marginBottom: 14,
  },
  sheetHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
    marginBottom: 14,
  },
  sheetDate: { fontSize: 18, fontWeight: "700", color: "#333" },
  lockedBadge: {
    backgroundColor: "#2ECC7122",
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  lockedBadgeText: { color: "#2ECC71", fontSize: 12, fontWeight: "600" },

  // Section
  sectionLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: "#888",
    paddingHorizontal: 20,
    marginBottom: 8,
    marginTop: 6,
  },

  // Chips
  chipRow: { paddingHorizontal: 16, paddingBottom: 12, gap: 8 },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: 20,
    backgroundColor: "#e8e8e8",
  },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 13, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },

  // Suggestions
  suggestionRow: { paddingHorizontal: 16, gap: 12 },
  sheetCenter: { height: 80, alignItems: "center", justifyContent: "center" },
  emptyText: { fontSize: 14, color: "#888" },

  // Suggestion card
  suggestionCard: {
    width: 200,
    backgroundColor: "#f9f9f9",
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 2,
    borderColor: "transparent",
  },
  suggestionCardLocked: { borderColor: "#2ECC71", backgroundColor: "#f0faf4" },
  suggestionThumbs: { flexDirection: "row", padding: 8, gap: 6 },
  suggestionReason: {
    fontSize: 12,
    color: "#666",
    fontStyle: "italic",
    paddingHorizontal: 10,
    marginBottom: 4,
  },
  suggestionFooter: {
    paddingHorizontal: 10,
    paddingBottom: 8,
  },
  suggestionScore: { fontSize: 13, fontWeight: "700", color: "#333" },

  // Lock button
  lockBtn: {
    backgroundColor: "#333",
    paddingVertical: 10,
    alignItems: "center",
  },
  lockBtnDone: { backgroundColor: "#e0e0e0" },
  lockBtnText: { color: "#fff", fontSize: 13, fontWeight: "600" },
  lockBtnTextDone: { color: "#888" },

  // Outfit thumb (inside sheet)
  outfitThumb: { position: "relative", borderRadius: 6, overflow: "hidden" },
  outfitThumbImg: {
    width: 50,
    height: 50,
    borderRadius: 6,
    backgroundColor: "#e0e0e0",
  },
  outfitThumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  outfitThumbInitial: { fontSize: 16, fontWeight: "700" },
  outfitThumbBadge: {
    position: "absolute",
    bottom: 2,
    left: 2,
    borderRadius: 3,
    paddingHorizontal: 4,
    paddingVertical: 1,
  },
  outfitThumbBadgeText: {
    color: "#fff",
    fontSize: 7,
    fontWeight: "700",
    textTransform: "uppercase",
  },
});
