import { useEffect, useState } from "react";
import { StyleSheet, Text, View, FlatList, TouchableOpacity, Alert } from "react-native";
import { clothingApi, ClothingItem } from "../../lib/api";

const CATEGORY_COLORS: Record<string, string> = {
  top: "#4A90D9",
  bottom: "#7B68EE",
  shoes: "#E8A317",
  accessory: "#E74C3C",
  outerwear: "#2ECC71",
};

export default function WardrobeScreen() {
  const [items, setItems] = useState<ClothingItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadItems = async () => {
    try {
      const data = await clothingApi.list();
      setItems(data);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadItems();
  }, []);

  const handleDelete = (item: ClothingItem) => {
    Alert.alert("Delete Item", `Remove "${item.name}" from wardrobe?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          await clothingApi.delete(item.id);
          setItems((prev) => prev.filter((i) => i.id !== item.id));
        },
      },
    ]);
  };

  const renderItem = ({ item }: { item: ClothingItem }) => (
    <TouchableOpacity style={styles.itemCard} onLongPress={() => handleDelete(item)}>
      <View style={[styles.categoryBadge, { backgroundColor: CATEGORY_COLORS[item.category] || "#999" }]}>
        <Text style={styles.categoryText}>{item.category}</Text>
      </View>
      <View style={styles.itemInfo}>
        <Text style={styles.itemName}>{item.name || "Unnamed"}</Text>
        <Text style={styles.itemDetails}>
          {[item.color, item.brand, item.season].filter(Boolean).join(" · ")}
        </Text>
      </View>
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <Text>Loading wardrobe...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {items.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>Your wardrobe is empty</Text>
          <Text style={styles.emptyText}>Go to "Add Item" tab to add your first piece.</Text>
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          renderItem={renderItem}
          contentContainerStyle={styles.list}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20 },
  list: { padding: 16 },
  itemCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  categoryBadge: { borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4, marginRight: 12 },
  categoryText: { color: "#fff", fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  itemInfo: { flex: 1 },
  itemName: { fontSize: 16, fontWeight: "600", marginBottom: 2 },
  itemDetails: { fontSize: 13, color: "#888" },
  emptyTitle: { fontSize: 18, fontWeight: "600", marginBottom: 6 },
  emptyText: { fontSize: 14, color: "#888", textAlign: "center" },
});
