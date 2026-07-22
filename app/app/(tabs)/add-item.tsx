import { useCallback, useEffect, useState } from "react";
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
import { router, useFocusEffect, useLocalSearchParams } from "expo-router";

import { BASE_URL } from "../../config/api";
import { clothingApi, consentApi, DEMO_USER_ID, TagResult, uploadApi } from "../../lib/api";

const CATEGORIES = ["top", "bottom", "dress", "outerwear", "footwear", "accessory"];
const PATTERNS = ["solid", "striped", "printed", "checked", "other"];
const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
const SEASONS = ["spring", "summer", "fall", "winter", "all-season"];
const TARGET_GENDERS = ["unisex", "men", "women"];
const FABRIC_TYPES = ["cotton", "denim", "silk", "wool", "leather", "linen", "knit", "synthetic"];
const FIT_TYPES = ["slim", "regular", "oversized", "loose"];
const SLEEVE_LENGTHS = ["sleeveless", "short", "three_quarter", "long", "not_applicable"];
const FORMALITY_MAP: Record<string, number> = {
  loungewear: 1, casual: 2, office: 3, party: 4, formal: 5, ethnic: 4,
};

export default function AddItemScreen() {
  const { image_url: routeImageUrl } = useLocalSearchParams<{ image_url?: string }>();
  const [consentChecked, setConsentChecked] = useState(false);
  const [step, setStep] = useState<"tagging" | "form" | "error">("form");
  const [errorMsg, setErrorMsg] = useState("");

  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [imageUri, setImageUri] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [color, setColor] = useState("");
  const [pattern, setPattern] = useState("");
  const [occasion, setOccasion] = useState<string[]>([]);
  const [season, setSeason] = useState("");
  const [targetGender, setTargetGender] = useState("unisex");
  const [fabricType, setFabricType] = useState("");
  const [fitType, setFitType] = useState("");
  const [sleeveLength, setSleeveLength] = useState("");
  const [formalityScore, setFormalityScore] = useState(0);
  const [showMore, setShowMore] = useState(false);
  const [needsReview, setNeedsReview] = useState<Record<string, boolean>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    consentApi
      .getStatus(DEMO_USER_ID)
      .then((status) => {
        if (!status.photo_consent) {
          router.replace("/consent");
        } else {
          setConsentChecked(true);
        }
      })
      .catch(() => setConsentChecked(true));
  }, []);

  useEffect(() => {
    if (routeImageUrl && routeImageUrl !== imageUrl) {
      setImageUrl(routeImageUrl);
      handleTagImage(routeImageUrl);
    }
  }, [routeImageUrl]);

  useFocusEffect(
    useCallback(() => {
      setImageUri(null);
    }, []),
  );

  const handleTagImage = async (url: string) => {
    setStep("tagging");
    setErrorMsg("");
    try {
      const tags = await uploadApi.tagItem(url);
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
    if (!review.occasion_tag) setOccasion(tags.occasion_tag ? tags.occasion_tag.split(",").map(s => s.trim()) : []);
    if (!review.season) setSeason(tags.season ?? "");
    if (!review.fabric_type) setFabricType(tags.fabric_type ?? "");
    if (!review.fit_type) setFitType(tags.fit_type ?? "");
    if (!review.sleeve_length) setSleeveLength(tags.sleeve_length ?? "");
    if (!review.target_gender) setTargetGender(tags.target_gender ?? "unisex");
    if (tags.formality_score != null) setFormalityScore(tags.formality_score);
  };

  const handleSave = async () => {
    if (!name.trim()) {
      Alert.alert("Missing name", "Please give this item a name.");
      return;
    }
    setSaving(true);
    const occasionStr = occasion.length ? occasion.join(",") : null;
    const autoFormality = occasion.length
      ? Math.max(...occasion.map(o => FORMALITY_MAP[o] || 3))
      : 0;
    try {
      await clothingApi.create({
        name: name.trim(),
        image_url: imageUrl,
        category,
        color: color.trim() || null,
        pattern: pattern || null,
        occasion_tag: occasionStr,
        season: season.trim() || null,
        target_gender: targetGender,
        fabric_type: fabricType || null,
        fit_type: fitType || null,
        sleeve_length: sleeveLength || null,
        formality_score: formalityScore || autoFormality || null,
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
    setImageUrl(null);
    setImageUri(null);
    setName("");
    setCategory("");
    setColor("");
    setPattern("");
    setOccasion([]);
    setSeason("");
    setTargetGender("unisex");
    setFabricType("");
    setFitType("");
    setSleeveLength("");
    setFormalityScore(0);
    setShowMore(false);
    setNeedsReview({});
    setStep("form");
  };

  const handleNavigateToCapture = () => {
    router.push("/capture?mode=item");
  };

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

  const renderMultiChips = (
    options: string[],
    selected: string[],
    onToggle: (v: string) => void,
    highlightReview = false,
  ) => (
    <View style={[styles.chipRow, highlightReview && styles.chipRowReview]}>
      {options.map((o) => (
        <TouchableOpacity
          key={o}
          style={[styles.chip, selected.includes(o) && styles.chipActive]}
          onPress={() => onToggle(o)}
        >
          <Text style={[styles.chipText, selected.includes(o) && styles.chipTextActive]}>
            {o}
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  if (!consentChecked) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color="#333" style={{ marginTop: 100 }} />
      </View>
    );
  }

  // Tagging step
  if (step === "tagging") {
    return (
      <View style={styles.container} accessibilityRole="progressbar" accessibilityLabel="Analyzing garment with AI">
        <View style={styles.loadingContent}>
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Analyzing with AI...</Text>
        </View>
      </View>
    );
  }

  // Error step
  if (step === "error") {
    return (
      <View style={styles.container}>
        <View style={styles.loadingContent}>
          <Text style={styles.errorTitle}>Tagging Failed</Text>
          <Text style={styles.errorDetail}>{errorMsg || "Failed to analyze image."}</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => {
              if (imageUrl) {
                setStep("form");
              } else {
                handleNavigateToCapture();
              }
            }}
          >
            <Text style={styles.buttonText}>Try Again</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // No image yet — show CTA
  if (!imageUrl) {
    return (
      <View style={styles.container}>
        <View style={styles.pickContent}>
          <Text style={styles.heading}>Add New Item</Text>
          <Text style={styles.subtitle}>
            Take a photo of your clothing to auto-tag it with AI.
          </Text>
          <TouchableOpacity style={styles.button} onPress={handleNavigateToCapture}>
            <Text style={styles.buttonText}>Take Photo</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // Form step
  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.formContent}>
      {imageUrl && (
        <Image source={{ uri: `${BASE_URL}${imageUrl}` }} style={styles.formImage} />
      )}

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

      <Text style={styles.label}>Occasion (select all that apply)</Text>
      {renderMultiChips(OCCASIONS, occasion, (v) => {
        setOccasion(prev =>
          prev.includes(v) ? prev.filter(x => x !== v) : [...prev, v]
        );
      }, needsReview.occasion_tag)}

      <Text style={styles.label}>Season</Text>
      {renderChips(SEASONS, season, setSeason, needsReview.season)}

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

        <TouchableOpacity style={styles.cancelButton} onPress={handleNavigateToCapture}>
          <Text style={styles.cancelButtonText}>Retake Photo</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  pickContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  heading: { fontSize: 24, fontWeight: "700", marginBottom: 8 },
  subtitle: { fontSize: 15, color: "#666", textAlign: "center", marginBottom: 32, lineHeight: 22 },
  loadingContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: 40 },
  loadingText: { fontSize: 16, color: "#666", marginTop: 12 },
  errorTitle: { fontSize: 18, fontWeight: "700", color: "#c00", marginTop: 16, marginBottom: 8 },
  errorDetail: { fontSize: 14, color: "#888", textAlign: "center", marginBottom: 24 },
  button: {
    width: "100%",
    backgroundColor: "#333",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  formImage: { width: "100%", height: 200, borderRadius: 12, marginBottom: 16 },
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
