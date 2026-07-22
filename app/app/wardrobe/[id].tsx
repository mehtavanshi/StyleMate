import { useEffect, useState } from "react";
import {
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useLocalSearchParams, useNavigation } from "expo-router";
import { clothingApi, ClothingItem } from "../../lib/api";
import { BASE_URL } from "../../config/api";
import { Sparkles } from "../../lib/icons";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../../theme/tokens";

const CATEGORY_COLORS: Record<string, string> = {
  top: "#4A90D9",
  bottom: "#7B68EE",
  dress: "#E91E8A",
  outerwear: "#2ECC71",
  footwear: "#E8A317",
  accessory: "#E74C3C",
};

export default function ItemDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const [item, setItem] = useState<ClothingItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: "Item Details", headerShown: true });
  }, [navigation]);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await clothingApi.get(Number(id));
        setItem(data);
      } catch (e: any) {
        Alert.alert("Error", e.message);
        router.back();
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleDelete = () => {
    if (!item) return;
    Alert.alert("Delete Item", `Remove "${item.name || "Unnamed"}" from wardrobe?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await clothingApi.delete(item.id);
            router.back();
          } catch (e: any) {
            Alert.alert("Error", e.message);
          }
        },
      },
    ]);
  };

  if (loading || !item) {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Loading item details">
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      </SafeAreaView>
    );
  }

  const TagRow = ({ label, value }: { label: string; value: string | null }) => {
    if (!value) return null;
    return (
      <View style={styles.tagRow}>
        <Text style={styles.tagLabel}>{label}</Text>
        <Text style={styles.tagValue}>{value}</Text>
      </View>
    );
  };

  return (
    <SafeAreaView style={{ flex: 1 }}>
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {item.image_url && !imgFailed ? (
        <Image
          source={{ uri: `${BASE_URL}${item.image_url}` }}
          style={styles.image}
          accessibilityLabel={`Image of ${item.name || "clothing item"}`}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <View style={[styles.image, styles.imagePlaceholder]} accessibilityLabel="Image unavailable">
          <Text style={styles.placeholderText}>{item.name?.[0] || "?"}</Text>
        </View>
      )}

      <View style={styles.infoSection}>
        <Text style={styles.name}>{item.name || "Unnamed Item"}</Text>
        <View style={[styles.categoryBadge, { backgroundColor: CATEGORY_COLORS[item.category] || "#999" }]}>
          <Text style={styles.categoryText}>{item.category}</Text>
        </View>
      </View>

      <View style={styles.tagsCard}>
        <TagRow label="Color" value={item.color} />
        <TagRow label="Pattern" value={item.pattern} />
        <TagRow label="Occasion" value={item.occasion_tag} />
        <TagRow label="Season" value={item.season} />
        <TagRow label="Brand" value={item.brand} />
        <TagRow label="Formality" value={item.formality} />
      </View>

      <TouchableOpacity
        style={styles.styleMatchButton}
        onPress={() => router.push(`/style-match?id=${item.id}`)}
      >
        <Text style={styles.styleMatchButtonText}><Sparkles size={18} color="#fff" strokeWidth={1.5} /> Style Match Suggestions</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.deleteButton} onPress={handleDelete}>
        <Text style={styles.deleteButtonText}>Delete from Wardrobe</Text>
      </TouchableOpacity>
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: spacing.xxl + spacing.sm },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { fontSize: fontSize.sm + 1, color: colors.text.tertiary },

  image: { width: "100%", height: 320, backgroundColor: "#ddd" },
  imagePlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { fontSize: fontSize.display, fontWeight: fontWeight.bold, color: colors.text.light },

  infoSection: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: spacing.lg },
  name: { fontSize: fontSize.xl, fontWeight: fontWeight.bold, flex: 1, marginRight: spacing.sm },
  categoryBadge: { borderRadius: br.sm + 2, paddingHorizontal: spacing.md, paddingVertical: spacing.xs + 1 },
  categoryText: { color: colors.text.white, fontSize: fontSize.xs, fontWeight: fontWeight.bold, textTransform: "uppercase" },

  tagsCard: { marginHorizontal: spacing.lg, backgroundColor: colors.surface, borderRadius: br.md, padding: spacing.xs },
  tagRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  tagLabel: { fontSize: fontSize.sm, color: colors.text.light, textTransform: "capitalize" },
  tagValue: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, color: colors.accent, textTransform: "capitalize" },

  styleMatchButton: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.xl,
    backgroundColor: colors.accent,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
  },
  styleMatchButtonText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  deleteButton: {
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.danger,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
  },
  deleteButtonText: { color: colors.danger, fontSize: fontSize.base, fontWeight: fontWeight.bold },
});
