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
const FABRIC_TYPES = ["cotton", "denim", "silk", "wool", "leather", "linen", "knit", "synthetic"];
const FIT_TYPES = ["slim", "regular", "oversized", "loose"];
const SLEEVE_LENGTHS = ["sleeveless", "short", "three_quarter", "long", "not_applicable"];

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
  const [fabricType, setFabricType] = useState("");
  const [fitType, setFitType] = useState("");
  const [sleeveLength, setSleeveLength] = useState("");
  const [formalityScore, setFormalityScore] = useState(0);
  const [showMore, setShowMore] = useState(false);

  const [needsReview, setNeedsReview] = useState<Record<string, boolean>>({});
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
    } catch (e: any) {
      setErrorMsg(e.message || "Failed to analyze image");
      setStep("error");
    }
  };

  const applyTags = (tags: TagResult) => {
    const review = tags._needs_review || {};
    setNeedsReview(review);
    if (!review.category) setCategory(tags.category ?? "");
    if (!review.dominant_color) setColor(tags.dominant_color ?? "");
    if (!review.pattern) setPattern(tags.pattern ?? "");
    if (!review.occasion_tag) setOccasion(tags.occasion_tag ?? "");
    if (!review.season) setSeason(tags.season ?? "");
    if (!review.fabric_type) setFabricType(tags.fabric_type ?? "");
    if (!review.fit_type) setFitType(tags.fit_type ?? "");
    if (!review.sleeve_length) setSleeveLength(tags.sleeve_length ?? "");
    if (tags.formality_score != null) setFormalityScore(tags.formality_score);
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
        fabric_type: fabricType || null,
        fit_type: fitType || null,
        sleeve_length: sleeveLength || null,
        formality_score: formalityScore || null,
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
    setFabricType("");
    setFitType("");
    setSleeveLength("");
    setFormalityScore(0);
    setShowMore(false);
    setNeedsReview({});
  };

  // ── Renderers ──

  const renderChips = (
    options: string[],
    value: string,
    onSelect: (v: string) => void,
    highlightReview = false,
  ) => (
    <View style={[styles.chipRow, highlightReview && styles.chipRowReview]}>
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
          <Text style={styles.errorTitle}>Tagging Failed</Text>
          <Text style={styles.errorDetail}>{errorMsg || "Tagging failed. Please retry or enter tags manually."}</Text>
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
      {renderChips(CATEGORIES, category, setCategory, needsReview.category)}

      <Text style={styles.label}>Color</Text>
      <TextInput
        style={[styles.input, needsReview.dominant_color && styles.inputReview]}
        value={color}
        onChangeText={setColor}
        placeholder="e.g. navy blue"
      />

      <Text style={styles.label}>Pattern</Text>
      {renderChips(PATTERNS, pattern, setPattern, needsReview.pattern)}

      <Text style={styles.label}>Occasion</Text>
      {renderChips(OCCASIONS, occasion, setOccasion, needsReview.occasion_tag)}

      <Text style={styles.label}>Season</Text>
      <TextInput
        style={[styles.input, needsReview.season && styles.inputReview]}
        value={season}
        onChangeText={setSeason}
        placeholder="e.g. winter, all-season"
      />

      <Text style={styles.label}>Target Gender</Text>
      {renderChips(TARGET_GENDERS, targetGender, setTargetGender, needsReview.target_gender)}

      <TouchableOpacity
        style={styles.moreToggle}
        onPress={() => setShowMore(!showMore)}
      >
        <Text style={styles.moreToggleText}>
          {showMore ? "Less details" : "More details"}
        </Text>
        <Text style={styles.moreToggleChevron}>{showMore ? "\u25B2" : "\u25BC"}</Text>
      </TouchableOpacity>

      {showMore && (
        <View style={styles.moreSection}>
          <Text style={styles.label}>Fabric Type</Text>
          {renderChips(FABRIC_TYPES, fabricType, setFabricType, needsReview.fabric_type)}

          <Text style={styles.label}>Fit Type</Text>
          {renderChips(FIT_TYPES, fitType, setFitType, needsReview.fit_type)}

          <Text style={styles.label}>Sleeve Length</Text>
          {renderChips(SLEEVE_LENGTHS, sleeveLength, setSleeveLength, needsReview.sleeve_length)}

          <Text style={styles.label}>Formality (1\u20135)</Text>
          <View style={styles.chipRow}>
            {[1, 2, 3, 4, 5].map((n) => (
              <TouchableOpacity
                key={n}
                style={[styles.chip, formalityScore === n && styles.chipActive]}
                onPress={() => setFormalityScore(n)}
              >
                <Text style={[styles.chipText, formalityScore === n && styles.chipTextActive]}>
                  {n}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      )}

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
  inputReview: {
    borderColor: "#e8b830",
    borderWidth: 2,
    backgroundColor: "#fffef5",
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  chipRowReview: {
    borderWidth: 2,
    borderColor: "#e8b830",
    borderRadius: 12,
    paddingVertical: 4,
    paddingHorizontal: 6,
    backgroundColor: "#fffef5",
  },
  chip: { paddingHorizontal: 16, paddingVertical: 8, borderRadius: 20, backgroundColor: "#e0e0e0" },
  chipActive: { backgroundColor: "#333" },
  chipText: { fontSize: 14, color: "#555", textTransform: "capitalize" },
  chipTextActive: { color: "#fff" },
  formActions: { marginTop: 30, gap: 12 },
  moreToggle: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 20,
    paddingVertical: 10,
  },
  moreToggleText: { fontSize: 15, fontWeight: "600", color: "#555", marginRight: 6 },
  moreToggleChevron: { fontSize: 12, color: "#555" },
  moreSection: {
    marginTop: 4,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: "#e0e0e0",
  },
  saveButton: { backgroundColor: "#333", borderRadius: 12, padding: 16, alignItems: "center" },
  saveButtonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  cancelButton: { alignItems: "center", padding: 12 },
  cancelButtonText: { color: "#888", fontSize: 15 },
});
