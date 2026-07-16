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
import { router, useLocalSearchParams } from "expo-router";
import { clothingApi, ClothingItem } from "../../lib/api";
import { BASE_URL } from "../../config/api";

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
  const [item, setItem] = useState<ClothingItem | null>(null);
  const [loading, setLoading] = useState(true);

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
      <View style={styles.center}>
        <Text style={styles.loadingText}>Loading...</Text>
      </View>
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
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {item.image_url ? (
        <Image source={{ uri: `${BASE_URL}${item.image_url}` }} style={styles.image} />
      ) : (
        <View style={[styles.image, styles.imagePlaceholder]}>
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

      <TouchableOpacity style={styles.deleteButton} onPress={handleDelete}>
        <Text style={styles.deleteButtonText}>Delete from Wardrobe</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  loadingText: { fontSize: 15, color: "#888" },

  image: { width: "100%", height: 320, backgroundColor: "#ddd" },
  imagePlaceholder: { alignItems: "center", justifyContent: "center" },
  placeholderText: { fontSize: 48, fontWeight: "700", color: "#999" },

  infoSection: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: 16 },
  name: { fontSize: 20, fontWeight: "700", flex: 1, marginRight: 10 },
  categoryBadge: { borderRadius: 8, paddingHorizontal: 12, paddingVertical: 5 },
  categoryText: { color: "#fff", fontSize: 12, fontWeight: "700", textTransform: "uppercase" },

  tagsCard: { marginHorizontal: 16, backgroundColor: "#fff", borderRadius: 12, padding: 4 },
  tagRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  tagLabel: { fontSize: 14, color: "#999", textTransform: "capitalize" },
  tagValue: { fontSize: 14, fontWeight: "600", color: "#333", textTransform: "capitalize" },

  deleteButton: {
    marginHorizontal: 16,
    marginTop: 24,
    backgroundColor: "#fff",
    borderWidth: 1.5,
    borderColor: "#E74C3C",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  deleteButtonText: { color: "#E74C3C", fontSize: 16, fontWeight: "700" },
});
