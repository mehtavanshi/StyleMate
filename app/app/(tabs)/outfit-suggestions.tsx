import { useCallback, useState } from "react";
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
import { router, useFocusEffect } from "expo-router";
import { outfitApi, OutfitSuggestion, OutfitItem } from "../../lib/api";
import { BASE_URL } from "../../config/api";

const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
const TARGET_GENDERS = ["unisex", "men", "women"];

const CATEGORY_COLORS: Record<string, string> = {
  top: "#4A90D9",
  bottom: "#7B68EE",
  dress: "#E91E8A",
  outerwear: "#2ECC71",
  footwear: "#E8A317",
  accessory: "#E74C3C",
};

function scoreColor(score: number): string {
  if (score >= 0.8) return "#2ECC71";
  if (score >= 0.5) return "#E8A317";
  return "#E74C3C";
}

function ItemThumb({ item }: { item: OutfitItem }) {
  const bg = CATEGORY_COLORS[item.category] || "#999";
  return (
    <TouchableOpacity
      style={styles.thumbWrap}
      activeOpacity={0.8}
      onPress={() => router.push(`/wardrobe/${item.id}`)}
    >
      {item.image_url ? (
        <Image source={{ uri: `${BASE_URL}${item.image_url}` }} style={styles.thumbImage} />
      ) : (
        <View style={[styles.thumbImage, styles.thumbPlaceholder, { backgroundColor: bg + "33" }]}>
          <Text style={[styles.thumbInitial, { color: bg }]}>
            {(item.name || item.category)?.[0]?.toUpperCase() || "?"}
          </Text>
        </View>
      )}
      <View style={[styles.thumbBadge, { backgroundColor: bg }]}>
        <Text style={styles.thumbBadgeText}>{item.category}</Text>
      </View>
      <View style={styles.thumbOverlay}>
        <Text style={styles.thumbName} numberOfLines={1}>{item.name || "Unnamed"}</Text>
      </View>
    </TouchableOpacity>
  );
}

export default function OutfitSuggestionsScreen() {
  const [suggestions, setSuggestions] = useState<OutfitSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOccasion, setSelectedOccasion] = useState<string | null>(null);
  const [selectedTargetGender, setSelectedTargetGender] = useState<string | null>(null);

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const data = await outfitApi.suggest({
        occasion_tag: selectedOccasion || undefined,
        target_gender: selectedTargetGender || undefined,
      });
      setSuggestions(data);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadSuggestions();
    }, [selectedOccasion, selectedTargetGender])
  );

  const renderCard = ({ item }: { item: OutfitSuggestion }) => (
    <View style={styles.card}>
      <View style={styles.cardImages}>
        {item.items.map((outfitItem, i) => (
          <View key={outfitItem.id} style={styles.thumbOuter}>
            <ItemThumb item={outfitItem} />
          </View>
        ))}
      </View>

      <View style={styles.cardFooter}>
        <Text style={styles.reasonText}>{item.reason}</Text>
        <View style={[styles.scoreBadge, { backgroundColor: scoreColor(item.score) + "22" }]}>
          <Text style={[styles.scoreText, { color: scoreColor(item.score) }]}>
            ★ {item.score.toFixed(2)}
          </Text>
        </View>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>Outfit Suggestions</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={loadSuggestions}>
          <Text style={styles.refreshBtnText}>↻ Refresh</Text>
        </TouchableOpacity>
      </View>

      {/* Occasion chips */}
      <View style={styles.chipBar}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={OCCASIONS}
          keyExtractor={(o) => o}
          contentContainerStyle={styles.chipList}
          renderItem={({ item: o }) => {
            const active = selectedOccasion === o;
            return (
              <TouchableOpacity
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setSelectedOccasion(active ? null : o)}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{o}</Text>
              </TouchableOpacity>
            );
          }}
        />
      </View>

      {/* Gender chips */}
      <View style={styles.chipBar}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={TARGET_GENDERS}
          keyExtractor={(g) => g}
          contentContainerStyle={styles.chipList}
          renderItem={({ item: g }) => {
            const active = selectedTargetGender === g;
            return (
              <TouchableOpacity
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setSelectedTargetGender(active ? null : g)}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{g}</Text>
              </TouchableOpacity>
            );
          }}
        />
      </View>

      {/* Content */}
      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Generating outfits...</Text>
        </View>
      ) : suggestions.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>No outfit suggestions</Text>
          <Text style={styles.emptyText}>
            {selectedOccasion
              ? `No outfits match the "${selectedOccasion}" occasion. Try clearing the filter.`
              : "Add items to your wardrobe to get outfit suggestions."}
          </Text>
        </View>
      ) : (
        <FlatList
          data={suggestions}
          keyExtractor={(item, i) => `suggestion-${i}`}
          contentContainerStyle={styles.list}
          renderItem={renderCard}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30 },
  loadingText: { fontSize: 14, color: "#888", marginTop: 10 },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#fff",
    borderBottomWidth: 1,
    borderBottomColor: "#eee",
  },
  title: { fontSize: 20, fontWeight: "700" },
  refreshBtn: {
    backgroundColor: "#333",
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  refreshBtnText: { color: "#fff", fontSize: 14, fontWeight: "600" },

  // Chips
  chipBar: { backgroundColor: "#fff", paddingBottom: 10, borderBottomWidth: 1, borderBottomColor: "#eee" },
  chipList: { paddingHorizontal: 12, paddingTop: 10 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: "#e8e8e8", marginRight: 8 },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 13, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },

  // List
  list: { padding: 12 },

  // Card
  card: {
    backgroundColor: "#fff",
    borderRadius: 14,
    overflow: "hidden",
    marginBottom: 14,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 4,
    elevation: 3,
  },
  cardImages: {
    flexDirection: "row",
    padding: 10,
    gap: 10,
  },
  thumbOuter: { flex: 1 },
  thumbWrap: { position: "relative", borderRadius: 10, overflow: "hidden" },
  thumbImage: { width: "100%", aspectRatio: 1, borderRadius: 10, backgroundColor: "#e0e0e0" },
  thumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  thumbInitial: { fontSize: 24, fontWeight: "700" },
  thumbBadge: {
    position: "absolute",
    top: 6,
    left: 6,
    borderRadius: 5,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  thumbBadgeText: { color: "#fff", fontSize: 9, fontWeight: "700", textTransform: "uppercase" },
  thumbOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0,0,0,0.4)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderBottomLeftRadius: 10,
    borderBottomRightRadius: 10,
  },
  thumbName: { color: "#fff", fontSize: 11, fontWeight: "600" },

  // Card footer
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: "#f0f0f0",
  },
  reasonText: { flex: 1, fontSize: 13, color: "#666", fontStyle: "italic", marginRight: 10 },
  scoreBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  scoreText: { fontSize: 13, fontWeight: "700" },

  // Empty
  emptyTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  emptyText: { fontSize: 14, color: "#888", textAlign: "center", lineHeight: 22 },
});
