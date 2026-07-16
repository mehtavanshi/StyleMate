import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import { router } from "expo-router";

import { clothingApi, TagResult, uploadApi } from "../../lib/api";

const CATEGORIES = ["top", "bottom", "dress", "outerwear", "footwear", "accessory"];
const PATTERNS = ["solid", "striped", "printed", "checked", "other"];
const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
const TARGET_GENDERS = ["unisex", "men", "women"];

export default function AddItemScreen() {
  const [step, setStep] = useState<"pick" | "loading" | "form" | "error">("pick");
  const [errorMsg, setErrorMsg] = useState("");

  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);

  // Editable AI-suggested fields
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [color, setColor] = useState("");
  const [pattern, setPattern] = useState("");
  const [occasion, setOccasion] = useState("");
  const [season, setSeason] = useState("");
  const [targetGender, setTargetGender] = useState("unisex");

  const [saving, setSaving] = useState(false);

  // ── Image picker ──

  const pickImage = async (useCamera: boolean) => {
    const permission = useCamera
      ? await ImagePicker.requestCameraPermissionsAsync()
      : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      Alert.alert("Permission needed", "Camera/gallery access is required to add items.");
      return;
    }

    const result = useCamera
      ? await ImagePicker.launchCameraAsync({
          mediaTypes: ["images"],
          quality: 0.8,
        })
      : await ImagePicker.launchImageLibraryAsync({
          mediaTypes: ["images"],
          quality: 0.8,
        });

    if (result.canceled) return;

    const asset = result.assets[0];
    setImageUri(asset.uri);
    await analyzeImage(asset);
  };

  // ── Upload + AI tagging ──

  const analyzeImage = async (asset: ImagePicker.ImagePickerAsset) => {
    setStep("loading");
    setErrorMsg("");

    try {
      const { image_url } = await uploadApi.uploadImage(
        asset.uri,
        asset.fileName || "item.jpg",
        asset.mimeType || "image/jpeg"
      );
      setImageUrl(image_url);

      const tags = await uploadApi.tagItem(image_url);
      applyTags(tags);
      setStep("form");
      if (tags._error) {
        Alert.alert(
          "AI Analysis Unavailable",
          "Auto-tagging failed. You can fill in the fields manually.\n\n" + tags._error
        );
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to analyze image");
      setStep("error");
    }
  };

  const applyTags = (tags: TagResult) => {
    setCategory(tags.category);
    setColor(tags.dominant_color);
    setPattern(tags.pattern);
    setOccasion(tags.occasion_tag);
    setSeason(tags.season);
  };

  // ── Save ──

  const handleSave = async () => {
    if (!name.trim()) {
      Alert.alert("Missing name", "Please give this item a name.");
      return;
    }
    setSaving(true);
    try {
      await clothingApi.create({
        name: name.trim(),
        image_url: imageUrl,
        category,
        color: color.trim() || null,
        pattern: pattern || null,
        occasion_tag: occasion || null,
        season: season.trim() || null,
        target_gender: targetGender,
      });
      resetForm();
      router.replace("/wardrobe");
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setStep("pick");
    setImageUri(null);
    setImageUrl(null);
    setName("");
    setCategory("");
    setColor("");
    setPattern("");
    setOccasion("");
    setSeason("");
    setTargetGender("unisex");
  };

  // ── Renderers ──

  const renderChips = (
    options: string[],
    value: string,
    onSelect: (v: string) => void
  ) => (
    <View style={styles.chipRow}>
      {options.map((o) => (
        <TouchableOpacity
          key={o}
          style={[styles.chip, value === o && styles.chipActive]}
          onPress={() => onSelect(o)}
        >
          <Text style={[styles.chipText, value === o && styles.chipTextActive]}>
            {o}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  // ── Pick step ──

  if (step === "pick") {
    return (
      <View style={styles.container}>
        <View style={styles.pickContent}>
          <Text style={styles.heading}>Add New Item</Text>
          <Text style={styles.subtitle}>
            Take a photo or pick one from your gallery to auto-tag it.
          </Text>

          <TouchableOpacity style={styles.pickButton} onPress={() => pickImage(true)}>
            <Text style={styles.pickButtonText}>Take Photo</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.pickButton, styles.pickButtonSecondary]}
            onPress={() => pickImage(false)}
          >
            <Text style={[styles.pickButtonText, styles.pickButtonTextSecondary]}>
              Pick from Gallery
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // ── Loading step ──

  if (step === "loading") {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContent}>
          {imageUri && (
            <Image source={{ uri: imageUri }} style={styles.previewImage} />
          )}
          <ActivityIndicator size="large" color="#333" style={{ marginTop: 20 }} />
          <Text style={styles.loadingText}>Analyzing with AI...</Text>
        </View>
      </View>
    );
  }

  // ── Error step ──

  if (step === "error") {
    return (
      <View style={styles.container}>
        <View style={styles.errorContent}>
          {imageUri && (
            <Image source={{ uri: imageUri }} style={styles.previewImage} />
          )}
          <Text style={styles.errorTitle}>Analysis Failed</Text>
          <Text style={styles.errorDetail}>{errorMsg}</Text>
          <TouchableOpacity
            style={styles.retryButton}
            onPress={() => {
              setStep("pick");
              setImageUri(null);
            }}
          >
            <Text style={styles.retryButtonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // ── Form step ──

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.formContent}>
      {imageUri && <Image source={{ uri: imageUri }} style={styles.formImage} />}

      <Text style={styles.label}>Name *</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Blue Denim Jacket"
      />

      <Text style={styles.label}>Category</Text>
      {renderChips(CATEGORIES, category, setCategory)}

      <Text style={styles.label}>Color</Text>
      <TextInput
        style={styles.input}
        value={color}
        onChangeText={setColor}
        placeholder="e.g. navy blue"
      />

      <Text style={styles.label}>Pattern</Text>
      {renderChips(PATTERNS, pattern, setPattern)}

      <Text style={styles.label}>Occasion</Text>
      {renderChips(OCCASIONS, occasion, setOccasion)}

      <Text style={styles.label}>Season</Text>
      <TextInput
        style={styles.input}
        value={season}
        onChangeText={setSeason}
        placeholder="e.g. winter, all-season"
      />

      <Text style={styles.label}>Target Gender</Text>
      {renderChips(TARGET_GENDERS, targetGender, setTargetGender)}

      <View style={styles.formActions}>
        <TouchableOpacity
          style={styles.saveButton}
          onPress={handleSave}
          disabled={saving}
        >
          <Text style={styles.saveButtonText}>
            {saving ? "Saving..." : "Add to Wardrobe"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.cancelButton} onPress={resetForm}>
          <Text style={styles.cancelButtonText}>Cancel</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },

  // Pick step
  pickContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  heading: { fontSize: 24, fontWeight: "700", marginBottom: 8 },
  subtitle: { fontSize: 15, color: "#666", textAlign: "center", marginBottom: 32, lineHeight: 22 },
  pickButton: {
    width: "100%",
    backgroundColor: "#333",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginBottom: 12,
  },
  pickButtonSecondary: { backgroundColor: "#fff", borderWidth: 1.5, borderColor: "#333" },
  pickButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  pickButtonTextSecondary: { color: "#333" },

  // Loading step
  loadingContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  loadingText: { fontSize: 16, color: "#666", marginTop: 12 },

  // Error step
  errorContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  errorTitle: { fontSize: 18, fontWeight: "700", color: "#c00", marginTop: 16, marginBottom: 8 },
  errorDetail: { fontSize: 14, color: "#888", textAlign: "center", marginBottom: 24 },
  retryButton: { backgroundColor: "#333", borderRadius: 12, paddingHorizontal: 40, paddingVertical: 14 },
  retryButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },

  // Common image
  previewImage: { width: 180, height: 180, borderRadius: 12 },
  formImage: { width: "100%", height: 200, borderRadius: 12, marginBottom: 16 },

  // Form step
  formContent: { padding: 20, paddingBottom: 40 },
  label: { fontSize: 14, fontWeight: "600", marginTop: 16, marginBottom: 6, color: "#333" },
  input: {
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    fontSize: 16,
    borderWidth: 1,
    borderColor: "#e0e0e0",
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: "#e0e0e0" },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 14, color: "#555", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },
  formActions: { marginTop: 30, gap: 12 },
  saveButton: { backgroundColor: "#333", borderRadius: 12, padding: 16, alignItems: "center" },
  saveButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  cancelButton: { alignItems: "center", padding: 12 },
  cancelButtonText: { color: "#888", fontSize: 15 },
});
