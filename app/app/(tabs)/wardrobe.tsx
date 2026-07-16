import { useCallback, useState, useMemo } from "react";
import {
  FlatList,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { router, useFocusEffect } from "expo-router";
import { clothingApi, ClothingItem } from "../../lib/api";
import { BASE_URL } from "../../config/api";

const CATEGORIES = ["top", "bottom", "dress", "outerwear", "footwear", "accessory"];
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

export default function WardrobeScreen() {
  const [items, setItems] = useState<ClothingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [selectedOccasions, setSelectedOccasions] = useState<Set<string>>(new Set());
  const [selectedTargetGenders, setSelectedTargetGenders] = useState<Set<string>>(new Set());

  const loadItems = async () => {
    try {
      const data = await clothingApi.list();
      setItems(data);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useFocusEffect(
    useCallback(() => {
      loadItems();
    }, [])
  );

  const toggleFilter = (value: string, setter: React.Dispatch<React.SetStateAction<Set<string>>>) => {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedCategories(new Set());
    setSelectedOccasions(new Set());
    setSelectedTargetGenders(new Set());
  };

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const catMatch = selectedCategories.size === 0 || selectedCategories.has(item.category);
      const occMatch = selectedOccasions.size === 0 || selectedOccasions.has(item.occasion_tag || "");
      const genderMatch = selectedTargetGenders.size === 0 || selectedTargetGenders.has(item.target_gender || "unisex");
      return catMatch && occMatch && genderMatch;
    });
  }, [items, selectedCategories, selectedOccasions, selectedTargetGenders]);

  const hasFilters = selectedCategories.size > 0 || selectedOccasions.size > 0 || selectedTargetGenders.size > 0;

  const renderChipRow = (
    label: string,
    options: string[],
    selected: Set<string>,
    setter: React.Dispatch<React.SetStateAction<Set<string>>>
  ) => (
    <View style={styles.filterSection}>
      <Text style={styles.filterLabel}>{label}</Text>
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={options}
        keyExtractor={(o) => o}
        contentContainerStyle={styles.chipList}
        renderItem={({ item: o }) => {
          const active = selected.has(o);
          return (
            <TouchableOpacity
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => toggleFilter(o, setter)}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{o}</Text>
            </TouchableOpacity>
          );
        }}
      />
    </View>
  );

  const renderItem = ({ item }: { item: ClothingItem }) => (
    <TouchableOpacity
      style={styles.gridCell}
      onPress={() => router.push(`/wardrobe/${item.id}`)}
      activeOpacity={0.8}
    >
      {item.image_url ? (
        <Image source={{ uri: `${BASE_URL}${item.image_url}` }} style={styles.gridImage} />
      ) : (
        <View style={[styles.gridImage, styles.gridImagePlaceholder]}>
          <Text style={styles.placeholderText}>{item.name?.[0] || "?"}</Text>
        </View>
      )}
      <View style={[styles.gridBadge, { backgroundColor: CATEGORY_COLORS[item.category] || "#999" }]}>
        <Text style={styles.gridBadgeText}>{item.category}</Text>
      </View>
      <View style={styles.gridOverlay}>
        <Text style={styles.gridName} numberOfLines={1}>{item.name || "Unnamed"}</Text>
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <Text style={styles.loadingText}>Loading wardrobe...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.filterBar}>
        {renderChipRow("Category", CATEGORIES, selectedCategories, setSelectedCategories)}
        {renderChipRow("Occasion", OCCASIONS, selectedOccasions, setSelectedOccasions)}
        {renderChipRow("Gender", TARGET_GENDERS, selectedTargetGenders, setSelectedTargetGenders)}
        {hasFilters && (
          <TouchableOpacity style={styles.clearBtn} onPress={clearFilters}>
            <Text style={styles.clearBtnText}>Clear filters</Text>
          </TouchableOpacity>
        )}
      </View>

      {filtered.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>
            {items.length === 0 ? "Your wardrobe is empty" : "No items match filters"}
          </Text>
          <Text style={styles.emptyText}>
            {items.length === 0
              ? 'Go to "Add Item" tab to add your first piece.'
              : "Try adjusting or clearing the filters."}
          </Text>
        </View>
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => String(item.id)}
          numColumns={2}
          columnWrapperStyle={styles.gridRow}
          contentContainerStyle={styles.gridContainer}
          renderItem={renderItem}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  loadingText: { fontSize: 15, color: "#888" },

  // Filter bar
  filterBar: { backgroundColor: "#fff", paddingBottom: 8, borderBottomWidth: 1, borderBottomColor: "#eee" },
  filterSection: { paddingTop: 10 },
  filterLabel: { fontSize: 12, fontWeight: "700", color: "#999", textTransform: "uppercase", paddingHorizontal: 16, marginBottom: 6 },
  chipList: { paddingHorizontal: 12 },
  chip: { paddingHorizontal: 14, paddingVertical: 7, borderRadius: 20, backgroundColor: "#e8e8e8", marginRight: 8 },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 13, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },
  clearBtn: { alignSelf: "center", marginTop: 6, paddingVertical: 4, paddingHorizontal: 12 },
  clearBtnText: { fontSize: 13, color: "#E74C3C", fontWeight: "600" },

  // Grid
  gridContainer: { padding: 8 },
  gridRow: { justifyContent: "space-between", marginBottom: 8 },
  gridCell: {
    flex: 1,
    marginHorizontal: 4,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#ddd",
    aspectRatio: 3 / 4,
  },
  gridImage: { width: "100%", height: "100%" },
  gridImagePlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { fontSize: 32, fontWeight: "700", color: "#999" },
  gridBadge: { position: "absolute", top: 8, left: 8, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 3 },
  gridBadgeText: { color: "#fff", fontSize: 10, fontWeight: "700", textTransform: "uppercase" },
  gridOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0,0,0,0.45)",
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  gridName: { color: "#fff", fontSize: 13, fontWeight: "600" },

  // Empty state
  emptyTitle: { fontSize: 18, fontWeight: "600", marginBottom: 6 },
  emptyText: { fontSize: 14, color: "#888", textAlign: "center" },
});
