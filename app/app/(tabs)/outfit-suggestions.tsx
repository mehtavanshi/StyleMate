import { useCallback, useState } from "react";
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
import { router, useFocusEffect } from "expo-router";
import * as Linking from "expo-linking";
import {
  outfitApi,
  feedbackApi,
  shoppingApi,
  OutfitSuggestion,
  OutfitItem,
  ShoppingGroup,
  ShoppingProduct,
} from "../../lib/api";
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

const BREAKDOWN_COLORS: Record<string, string> = {
  color: "#4A90D9",
  embedding: "#9B59B6",
  hard_rules: "#2ECC71",
  fabric: "#E8A317",
  fit: "#E74C3C",
  season: "#1ABC9C",
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
      {item.fabric_type && (
        <View style={[styles.attrBadge, { top: 26, backgroundColor: bg + "bb" }]}>
          <Text style={styles.attrBadgeText}>{item.fabric_type}</Text>
        </View>
      )}
      {item.fit_type && (
        <View style={[styles.attrBadge, { top: 44, backgroundColor: bg + "88" }]}>
          <Text style={styles.attrBadgeText}>{item.fit_type}</Text>
        </View>
      )}
      <View style={styles.thumbOverlay}>
        <Text style={styles.thumbName} numberOfLines={1}>{item.name || "Unnamed"}</Text>
      </View>
    </TouchableOpacity>
  );
}

function BreakdownBar({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  if (total === 0 || entries.length === 0) return null;
  return (
    <View style={styles.breakdownRow}>
      {entries.map(([key, value]) => {
        const color = BREAKDOWN_COLORS[key] || "#999";
        const pct = Math.max((value / total) * 100, 4);
        return (
          <View
            key={key}
            style={[styles.breakdownSegment, { flex: pct, backgroundColor: color }]}
          />
        );
      })}
    </View>
  );
}

function BreakdownLegend({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown);
  return (
    <View style={styles.legendRow}>
      {entries.map(([key, value]) => (
        <View key={key} style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: BREAKDOWN_COLORS[key] || "#999" }]} />
          <Text style={styles.legendLabel}>{key}</Text>
          <Text style={styles.legendValue}>{value.toFixed(2)}</Text>
        </View>
      ))}
    </View>
  );
}

export default function OutfitSuggestionsScreen() {
  const [suggestions, setSuggestions] = useState<OutfitSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOccasion, setSelectedOccasion] = useState<string | null>(null);
  const [selectedTargetGender, setSelectedTargetGender] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, boolean>>({});
  const [pendingFeedback, setPendingFeedback] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);
  const [shoppingGroups, setShoppingGroups] = useState<ShoppingGroup[]>([]);
  const [shoppingLoading, setShoppingLoading] = useState(true);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1800);
  };

  const loadShopping = async () => {
    setShoppingLoading(true);
    try {
      const data = await shoppingApi.suggest({
        target_gender: selectedTargetGender || undefined,
        occasion_tag: selectedOccasion || undefined,
      });
      setShoppingGroups(data);
    } catch (e: any) {
      // Non-fatal: the outfit suggestions still work without shopping.
      console.warn("Shopping suggestions failed:", e.message);
      setShoppingGroups([]);
    } finally {
      setShoppingLoading(false);
    }
  };

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
      loadShopping();
    }, [selectedOccasion, selectedTargetGender])
  );

  const submitFeedback = async (key: string, itemIds: number[], liked: boolean) => {
    if (feedbackGiven[key] || pendingFeedback[key]) return;
    setPendingFeedback((p) => ({ ...p, [key]: true }));
    try {
      await feedbackApi.create(itemIds, liked);
      setFeedbackGiven((g) => ({ ...g, [key]: true }));
      showToast(liked ? "Liked outfit 👍" : "Noted — outfit disliked 👎");
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setPendingFeedback((p) => ({ ...p, [key]: false }));
    }
  };

  const renderCard = ({ item, index }: { item: OutfitSuggestion; index: number }) => {
    const key = `suggestion-${index}`;
    const given = feedbackGiven[key];
    const pending = pendingFeedback[key];
    const itemIds = item.items.map((o) => o.id);
    return (
      <View style={[styles.card, given && styles.cardFeedbackGiven]}>
        <View style={styles.cardImages}>
          {item.items.map((outfitItem) => (
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
        <BreakdownBar breakdown={item.breakdown || {}} />
        <BreakdownLegend breakdown={item.breakdown || {}} />

        <View style={styles.feedbackRow}>
          <TouchableOpacity
            style={[styles.feedbackBtn, given && styles.feedbackBtnDisabled]}
            disabled={given || pending}
            onPress={() => submitFeedback(key, itemIds, true)}
          >
            <Text style={[styles.feedbackBtnText, given && styles.feedbackBtnTextDone]}>
              {given ? "👍 Saved" : "👍 Like"}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.feedbackBtn, styles.feedbackBtnDislike, given && styles.feedbackBtnDisabled]}
            disabled={given || pending}
            onPress={() => submitFeedback(key, itemIds, false)}
          >
            <Text style={[styles.feedbackBtnText, given && styles.feedbackBtnTextDone]}>
              {given ? "👎 Saved" : "👎 Dislike"}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.tryonRow}>
          <TouchableOpacity
            style={styles.tryonBtn}
            onPress={() => {
              const firstItem = item.items[0];
              if (firstItem) {
                router.push(`/try-on?garment_id=${firstItem.id}`);
              }
            }}
          >
            <Text style={styles.tryonBtnText}>✨ Try It On</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const openAffiliate = async (link: string) => {
    if (!link) return;
    try {
      const supported = await Linking.canOpenURL(link);
      if (supported) {
        await Linking.openURL(link);
      } else {
        Alert.alert("Can't open link", link);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  const renderProductCard = ({ item }: { item: ShoppingProduct }) => {
    // Meesho is a deep-link fallback (no real product API), so render it
    // distinctly as a "search" button — never as a specific product card
    // with price/image, which would mislead the user.
    if (item.source === "meesho") {
      return (
        <TouchableOpacity
          style={styles.meeshoButton}
          activeOpacity={0.85}
          onPress={() => openAffiliate(item.affiliate_link)}
        >
          <Text style={styles.meeshoButtonText}>🔍 Search this on Meesho</Text>
          <Text style={styles.meeshoButtonSub} numberOfLines={1}>
            {item.name}
          </Text>
        </TouchableOpacity>
      );
    }

    return (
      <TouchableOpacity
        style={styles.productCard}
        activeOpacity={0.85}
        onPress={() => openAffiliate(item.affiliate_link)}
      >
        {item.image_url ? (
          <Image source={{ uri: item.image_url }} style={styles.productImage} />
        ) : (
          <View style={[styles.productImage, styles.productImagePlaceholder]}>
            <Text style={styles.productInitial}>
              {(item.name || "?")[0]?.toUpperCase()}
            </Text>
          </View>
        )}
        <Text style={styles.productName} numberOfLines={2}>
          {item.name}
        </Text>
        <Text style={styles.productPrice}>
          {item.currency} {item.price.toFixed(2)}
        </Text>
      </TouchableOpacity>
    );
  };

  const CompleteTheLook = () => {
    if (shoppingLoading) {
      return (
        <View style={styles.shoppingSection}>
          <Text style={styles.shoppingHeading}>Complete the Look</Text>
          <View style={styles.shoppingRow}>
            {[0, 1, 2].map((i) => (
              <View key={i} style={styles.productCard}>
                <View style={[styles.productImage, styles.skeleton]} />
                <View style={[styles.skeletonLine, { width: "80%" }]} />
                <View style={[styles.skeletonLine, { width: "50%" }]} />
              </View>
            ))}
          </View>
        </View>
      );
    }

    if (!shoppingGroups || shoppingGroups.length === 0) {
      return (
        <View style={styles.shoppingSection}>
          <Text style={styles.shoppingHeading}>Complete the Look</Text>
          <Text style={styles.shoppingEmpty}>
            No suggestions right now — your wardrobe looks well rounded!
          </Text>
        </View>
      );
    }

    return (
      <View style={styles.shoppingSection}>
        <Text style={styles.shoppingHeading}>Complete the Look</Text>
        {shoppingGroups.map((group, gi) => (
          <View key={`${group.missing_category}-${gi}`} style={styles.gapBlock}>
            <Text style={styles.gapReason}>{group.gap_reason}</Text>
            {group.products.length === 0 ? (
              <Text style={styles.gapNoProducts}>
                No matches found right now.
              </Text>
            ) : (
              <FlatList
                horizontal
                showsHorizontalScrollIndicator={false}
                data={group.products}
                keyExtractor={(p, i) => `${group.missing_category}-${i}`}
                contentContainerStyle={styles.shoppingRow}
                renderItem={renderProductCard}
              />
            )}
          </View>
        ))}
      </View>
    );
  };

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
        <ScrollView contentContainerStyle={styles.list}>
          {suggestions.map((item, index) => (
            <View key={`suggestion-${index}`}>{renderCard({ item, index })}</View>
          ))}
          <CompleteTheLook />
        </ScrollView>
      )}

      <Modal visible={toast !== null} transparent animationType="fade">
        <View style={styles.toastWrap}>
          <View style={styles.toastBox}>
            <Text style={styles.toastText}>{toast}</Text>
          </View>
        </View>
      </Modal>
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
  cardFeedbackGiven: { opacity: 0.6 },
  feedbackRow: {
    flexDirection: "row",
    gap: 10,
    paddingHorizontal: 14,
    paddingBottom: 14,
    paddingTop: 6,
  },
  feedbackBtn: {
    flex: 1,
    backgroundColor: "#2ECC7155",
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#2ECC71",
  },
  feedbackBtnDislike: {
    backgroundColor: "#E74C3C33",
    borderColor: "#E74C3C",
  },
  feedbackBtnDisabled: {
    backgroundColor: "#eeeeee",
    borderColor: "#cccccc",
  },
  feedbackBtnText: { fontSize: 14, fontWeight: "700", color: "#1c1c1c" },
  feedbackBtnTextDone: { color: "#999" },

  // Toast
  toastWrap: {
    flex: 1,
    justifyContent: "flex-end",
    alignItems: "center",
    paddingBottom: 40,
    backgroundColor: "transparent",
  },
  toastBox: {
    backgroundColor: "rgba(0,0,0,0.82)",
    borderRadius: 12,
    paddingHorizontal: 20,
    paddingVertical: 12,
    maxWidth: "85%",
  },
  toastText: { color: "#fff", fontSize: 14, fontWeight: "600", textAlign: "center" },
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
  attrBadge: {
    position: "absolute",
    left: 6,
    borderRadius: 4,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  attrBadgeText: { color: "#fff", fontSize: 8, fontWeight: "600", textTransform: "uppercase" },
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

  // Breakdown
  // Try On
  tryonRow: {
    paddingHorizontal: 14,
    paddingBottom: 14,
  },
  tryonBtn: {
    backgroundColor: "#333",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
  },
  tryonBtnText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "700",
  },

  breakdownRow: {
    flexDirection: "row",
    height: 4,
    marginHorizontal: 14,
    marginBottom: 6,
    borderRadius: 2,
    overflow: "hidden",
    backgroundColor: "#eee",
  },
  breakdownSegment: {
    height: "100%",
  },
  legendRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: 14,
    paddingBottom: 10,
    gap: 8,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 3 },
  legendDot: { width: 6, height: 6, borderRadius: 3 },
  legendLabel: { fontSize: 10, color: "#888", textTransform: "capitalize" },
  legendValue: { fontSize: 10, color: "#555", fontWeight: "600" },

  // Complete the Look
  shoppingSection: {
    backgroundColor: "#fff",
    marginTop: 6,
    paddingVertical: 14,
    borderTopWidth: 1,
    borderTopColor: "#eee",
  },
  shoppingHeading: {
    fontSize: 17,
    fontWeight: "700",
    paddingHorizontal: 16,
    marginBottom: 12,
  },
  shoppingRow: { paddingHorizontal: 16, gap: 12 },
  shoppingEmpty: {
    fontSize: 14,
    color: "#888",
    paddingHorizontal: 16,
    lineHeight: 22,
  },
  gapBlock: { marginBottom: 18 },
  gapReason: {
    fontSize: 13,
    color: "#444",
    fontStyle: "italic",
    paddingHorizontal: 16,
    marginBottom: 10,
  },
  gapNoProducts: {
    fontSize: 13,
    color: "#aaa",
    paddingHorizontal: 16,
  },
  productCard: {
    width: 140,
    backgroundColor: "#fff",
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#eee",
    padding: 8,
  },
  meeshoButton: {
    width: 160,
    backgroundColor: "#fff",
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: "#E5408A",
    paddingVertical: 14,
    paddingHorizontal: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  meeshoButtonText: {
    fontSize: 13,
    fontWeight: "700",
    color: "#E5408A",
    textAlign: "center",
  },
  meeshoButtonSub: {
    fontSize: 11,
    color: "#999",
    marginTop: 4,
    textAlign: "center",
  },
  productImage: {
    width: "100%",
    height: 120,
    borderRadius: 8,
    backgroundColor: "#e0e0e0",
    marginBottom: 8,
  },
  productImagePlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  productInitial: { fontSize: 28, fontWeight: "700", color: "#999" },
  productName: { fontSize: 12, color: "#333", height: 32, marginBottom: 4 },
  productPrice: { fontSize: 13, fontWeight: "700", color: "#2ECC71" },
  skeleton: { backgroundColor: "#e6e6e6" },
  skeletonLine: {
    height: 10,
    borderRadius: 4,
    backgroundColor: "#e6e6e6",
    marginBottom: 6,
  },
});
