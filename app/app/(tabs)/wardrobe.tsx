import { useCallback, useState, useMemo } from "react";
import {
  Alert,
  FlatList,
  Image,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../../theme/tokens";
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

function WardrobeGridCell({ item }: { item: ClothingItem }) {
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <TouchableOpacity
      style={styles.gridCell}
      onPress={() => router.push(`/wardrobe/${item.id}`)}
      activeOpacity={0.8}
      accessibilityLabel={`${item.name || "Unnamed"} - ${item.category}`}
    >
      {item.image_url && !imgFailed ? (
        <Image
          source={{ uri: `${BASE_URL}${item.image_url}` }}
          style={styles.gridImage}
          onError={() => setImgFailed(true)}
        />
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
}

export default function WardrobeScreen() {
  const [items, setItems] = useState<ClothingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<Set<string>>(new Set());
  const [selectedOccasions, setSelectedOccasions] = useState<Set<string>>(new Set());
  const [selectedTargetGenders, setSelectedTargetGenders] = useState<Set<string>>(new Set());

  const loadItems = async () => {
    try {
      const data = await clothingApi.list();
      setItems(data);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Failed to load wardrobe.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const data = await clothingApi.list();
      setItems(data);
    } catch (e: any) {
      Alert.alert("Error", e.message || "Failed to load wardrobe.");
    } finally {
      setRefreshing(false);
    }
  }, []);

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
      const searchMatch = !search.trim() || (item.name || "").toLowerCase().includes(search.toLowerCase());
      const catMatch = selectedCategories.size === 0 || selectedCategories.has(item.category);
      const itemOccasions = (item.occasion_tag || "").split(",").map(s => s.trim());
      const occMatch = selectedOccasions.size === 0 || itemOccasions.some(o => selectedOccasions.has(o));
      const genderMatch = selectedTargetGenders.size === 0 || selectedTargetGenders.has(item.target_gender || "unisex");
      return searchMatch && catMatch && occMatch && genderMatch;
    });
  }, [items, search, selectedCategories, selectedOccasions, selectedTargetGenders]);

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
    <WardrobeGridCell item={item} />
  );

  if (loading) {
    return (
      <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Loading your wardrobe">
        <Text style={styles.loadingText}>Loading wardrobe...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.filterBar}>
        <TextInput
          style={styles.searchInput}
          placeholder="Search items..."
          placeholderTextColor={colors.text.muted}
          value={search}
          onChangeText={setSearch}
          clearButtonMode="while-editing"
        />
        {renderChipRow("Category", CATEGORIES, selectedCategories, setSelectedCategories)}
        {renderChipRow("Occasion", OCCASIONS, selectedOccasions, setSelectedOccasions)}
        {renderChipRow("Gender", TARGET_GENDERS, selectedTargetGenders, setSelectedTargetGenders)}
        {(hasFilters || search.trim()) && (
          <TouchableOpacity style={styles.clearBtn} onPress={() => { clearFilters(); setSearch(""); }}>
            <Text style={styles.clearBtnText}>Clear all</Text>
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
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.accent} />
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  loadingText: { fontSize: fontSize.sm + 1, color: colors.text.tertiary },

  // Filter bar
  filterBar: { backgroundColor: colors.surface, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  searchInput: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm + 2,
    marginBottom: spacing.xs,
    backgroundColor: "#f0f0f0",
    borderRadius: br.sm + 2,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.sm + 1,
    color: colors.text.primary,
  },
  filterSection: { paddingTop: spacing.sm + 2 },
  filterLabel: { fontSize: fontSize.xs, fontWeight: fontWeight.bold, color: colors.text.light, textTransform: "uppercase", paddingHorizontal: spacing.lg, marginBottom: spacing.xs + 2 },
  chipList: { paddingHorizontal: spacing.md },
  chip: { paddingHorizontal: spacing.sm + 6, paddingVertical: spacing.xs + 3, borderRadius: 20, backgroundColor: "#e8e8e8", marginRight: spacing.sm },
  chipActive: { backgroundColor: colors.accent },
  chipText: { fontSize: fontSize.xs + 1, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: colors.text.white },
  clearBtn: { alignSelf: "center", marginTop: spacing.xs + 2, paddingVertical: spacing.xs, paddingHorizontal: spacing.md },
  clearBtnText: { fontSize: fontSize.xs + 1, color: colors.danger, fontWeight: fontWeight.semibold },

  // Grid
  gridContainer: { padding: spacing.sm },
  gridRow: { justifyContent: "space-between", marginBottom: spacing.sm },
  gridCell: {
    flex: 1,
    marginHorizontal: spacing.xs,
    borderRadius: br.md,
    overflow: "hidden",
    backgroundColor: "#ddd",
    aspectRatio: 3 / 4,
  },
  gridImage: { width: "100%", height: "100%" },
  gridImagePlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { fontSize: fontSize.xxxl, fontWeight: fontWeight.bold, color: colors.text.light },
  gridBadge: { position: "absolute", top: spacing.sm, left: spacing.sm, borderRadius: br.sm, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs - 1 },
  gridBadgeText: { color: colors.text.white, fontSize: fontSize.xs - 2, fontWeight: fontWeight.bold, textTransform: "uppercase" },
  gridOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0,0,0,0.45)",
    paddingHorizontal: spacing.sm + 2,
    paddingVertical: spacing.sm,
  },
  gridName: { color: colors.text.white, fontSize: fontSize.xs + 1, fontWeight: fontWeight.semibold },

  // Empty state
  emptyTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.semibold, marginBottom: spacing.xs + 2 },
  emptyText: { fontSize: fontSize.sm, color: colors.text.tertiary, textAlign: "center" },
});
