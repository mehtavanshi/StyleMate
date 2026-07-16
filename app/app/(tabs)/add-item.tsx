import { useState } from "react";
import { StyleSheet, Text, View, TextInput, TouchableOpacity, Alert, ScrollView } from "react-native";
import { clothingApi } from "../../lib/api";

const CATEGORIES = ["top", "bottom", "shoes", "accessory", "outerwear"];
const SEASONS = ["spring", "summer", "fall", "winter", "all"];

export default function AddItemScreen() {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("top");
  const [color, setColor] = useState("");
  const [brand, setBrand] = useState("");
  const [season, setSeason] = useState("all");
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!name.trim()) {
      Alert.alert("Missing name", "Please enter a name for the item.");
      return;
    }
    setSaving(true);
    try {
      await clothingApi.create({
        name: name.trim(),
        category,
        color: color.trim() || null,
        brand: brand.trim() || null,
        season,
      });
      Alert.alert("Saved", `"${name}" added to your wardrobe!`);
      setName("");
      setColor("");
      setBrand("");
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.label}>Name *</Text>
      <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="e.g. Blue Denim Jacket" />

      <Text style={styles.label}>Category</Text>
      <View style={styles.chipRow}>
        {CATEGORIES.map((c) => (
          <TouchableOpacity
            key={c}
            style={[styles.chip, category === c && styles.chipActive]}
            onPress={() => setCategory(c)}
          >
            <Text style={[styles.chipText, category === c && styles.chipTextActive]}>{c}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>Color</Text>
      <TextInput style={styles.input} value={color} onChangeText={setColor} placeholder="e.g. navy blue" />

      <Text style={styles.label}>Brand</Text>
      <TextInput style={styles.input} value={brand} onChangeText={setBrand} placeholder="e.g. Nike" />

      <Text style={styles.label}>Season</Text>
      <View style={styles.chipRow}>
        {SEASONS.map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.chip, season === s && styles.chipActive]}
            onPress={() => setSeason(s)}
          >
            <Text style={[styles.chipText, season === s && styles.chipTextActive]}>{s}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity style={styles.saveButton} onPress={handleSave} disabled={saving}>
        <Text style={styles.saveButtonText}>{saving ? "Saving..." : "Add to Wardrobe"}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 20 },
  label: { fontSize: 14, fontWeight: "600", marginTop: 16, marginBottom: 6, color: "#333" },
  input: { backgroundColor: "#fff", borderRadius: 10, padding: 14, fontSize: 16, borderWidth: 1, borderColor: "#e0e0e0" },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: "#e0e0e0" },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 14, color: "#555", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },
  saveButton: { marginTop: 30, backgroundColor: "#333", borderRadius: 12, padding: 16, alignItems: "center" },
  saveButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
