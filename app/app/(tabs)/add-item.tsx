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
import { SafeAreaView } from "react-native-safe-area-context";

const SCREEN_EDGES = ["left", "right", "bottom"] as const;
import { ChevronDown, ChevronUp } from "../../lib/icons";
import { spacing, fontSize, fontWeight, borderRadius as br, colors } from "../../theme/tokens";
import { useTabScreenPadding } from "../../lib/useTabScreenPadding";
import { router, useLocalSearchParams } from "expo-router";

import { BASE_URL } from "../../config/api";
import { clothingApi, consentApi, DEMO_USER_ID, TagResult, uploadApi } from "../../lib/api";
import { resolveImageUrl } from "../../lib/constants";

const CATEGORIES = ["top", "bottom", "dress", "outerwear", "footwear", "accessory"];
const PATTERNS = ["solid", "striped", "printed", "checked", "other"];
const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
const SEASONS = ["spring", "summer", "fall", "winter", "all-season"];
const TARGET_GENDERS = ["unisex", "men", "women"];
const FABRIC_TYPES = ["cotton", "denim", "silk", "wool", "leather", "linen", "knit", "synthetic"];
const FIT_TYPES = ["slim", "regular", "oversized", "loose"];
const SLEEVE_LENGTHS = ["sleeveless", "short", "three_quarter", "long", "not_applicable"];
const SUBCATEGORY_OPTIONS: Record<string, string[]> = {
  top: ["none", "crop_top", "regular_top", "waist_length_top", "tunic", "maxi_top", "peplum_top", "off_shoulder_top", "tube_top", "halter_top"],
  bottom: ["none", "skinny", "straight_leg", "bootcut", "flare", "wide_leg", "baggy_mom", "boyfriend", "barrel_leg", "mini_skirt", "midi_skirt", "maxi_skirt", "a_line_skirt", "pencil_skirt", "pleated_skirt", "wrap_skirt", "shorts", "biker_shorts", "palazzo", "culottes", "joggers", "cargo_pants", "trousers"],
  kurti: ["none", "kurti_short", "kurti_long", "anarkali", "saree", "lehenga", "salwar_kameez", "palazzo_suit"],
  accessory: ["none", "bangles", "jhumkas", "maang_tikka", "potli_bag", "juttis", "nose_ring", "waist_belt", "dupatta"],
};
const GARMENT_LENGTHS = ["none", "cropped", "waist", "hip", "knee", "midi", "ankle", "floor"];
const EMBELLISHMENTS = ["none", "ribbon", "bow", "sequins", "lace", "tassel", "mirror_work", "buttons", "fringe", "beads"];
const FORMALITY_LABELS: Record<number, string> = { 1: "loungewear", 2: "casual", 3: "smart casual", 4: "dressy", 5: "formal" };
const FORMALITY_TO_SCORE: Record<string, number> = { loungewear: 1, casual: 2, "smart casual": 3, dressy: 4, formal: 5 };
// NOTE: This map is duplicated in server/app/routers/tagging.py:86 (Python).
// Both must stay in sync — this copy derives formality_score from the
// multi-select occasion chips before save; the backend copy is used in
// the tagging pipeline. If you add/remove/revalue an occasion here,
// update the other copy too.  TODO: replace with a shared GET /formality-map endpoint.
const FORMALITY_MAP: Record<string, number> = {
  loungewear: 1, casual: 2, office: 3, party: 4, formal: 5, ethnic: 4,
};

export default function AddItemScreen() {
  const { paddingBottom } = useTabScreenPadding();
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
  const [subcategory, setSubcategory] = useState("none");
  const [garmentLength, setGarmentLength] = useState("none");
  const [embellishments, setEmbellishments] = useState<string[]>(["none"]);
  const [showMore, setShowMore] = useState(false);
  const [needsReview, setNeedsReview] = useState<Record<string, boolean>>({});
  const [formality, setFormality] = useState("none");
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
    if (!review.subcategory) setSubcategory(tags.subcategory ?? "none");
    if (!review.garment_length) setGarmentLength(tags.garment_length ?? "none");
    if (!review.embellishments) {
      try {
        const parsed = JSON.parse(tags.embellishments ?? "[]");
        setEmbellishments(Array.isArray(parsed) && parsed.length > 0 ? parsed : ["none"]);
      } catch {
        setEmbellishments(["none"]);
      }
    }
    if (!review.formality_score && tags.formality_score != null) {
      setFormality(FORMALITY_LABELS[tags.formality_score] ?? "none");
    }
  };

  const handleSave = async () => {
    if (!name.trim()) {
      Alert.alert("Missing name", "Please give this item a name.");
      return;
    }
    setSaving(true);
    const occasionStr = occasion.length ? occasion.join(",") : null;
    const subcatVal = subcategory === "none" ? null : subcategory;
    const glVal = garmentLength === "none" ? null : garmentLength;
    const embVal = embellishments.includes("none") || embellishments.length === 0
      ? "[]"
      : JSON.stringify(embellishments);
    const derivedFormalityScore = formality !== "none"
      ? FORMALITY_TO_SCORE[formality] ?? null
      : occasion.length
        ? Math.max(...occasion.map(o => FORMALITY_MAP[o] || 3))
        : null;
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
        subcategory: subcatVal,
        garment_length: glVal,
        embellishments: embVal,
        formality_score: derivedFormalityScore,
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
    setSubcategory("none");
    setGarmentLength("none");
    setEmbellishments(["none"]);
    setFormality("none");

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
      <SafeAreaView edges={SCREEN_EDGES} style={{ flex: 1 }}>
        <View style={styles.container}>
          <ActivityIndicator size="large" color="#333" style={{ marginTop: 100 }} />
        </View>
      </SafeAreaView>
    );
  }

  // Tagging step
  if (step === "tagging") {
    return (
      <SafeAreaView edges={SCREEN_EDGES} style={{ flex: 1 }}>
        <View style={styles.container} accessibilityRole="progressbar" accessibilityLabel="Analyzing garment with AI">
          <View style={styles.loadingContent}>
            <ActivityIndicator size="large" color="#333" />
            <Text style={styles.loadingText}>Analyzing with AI...</Text>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // Error step
  if (step === "error") {
    return (
      <SafeAreaView edges={SCREEN_EDGES} style={{ flex: 1 }}>
        <View style={styles.container}>
          <View style={styles.loadingContent}>
            <Text style={styles.errorTitle}>Tagging Failed</Text>
            <Text style={styles.errorDetail}>{errorMsg || "Failed to analyze image."}</Text>
            <TouchableOpacity
              style={styles.button}
              onPress={() => {
                // Re-tag the image that's already uploaded rather than sending
                // the user back through capture and storing a second copy.
                if (imageUrl) {
                  handleTagImage(imageUrl);
                } else {
                  handleNavigateToCapture();
                }
              }}
            >
              <Text style={styles.buttonText}>Try Again</Text>
            </TouchableOpacity>
            {imageUrl && (
              <TouchableOpacity onPress={() => setStep("form")}>
                <Text style={styles.errorDetail}>Fill in the details myself</Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // No image yet — show CTA
  if (!imageUrl) {
    return (
      <SafeAreaView edges={SCREEN_EDGES} style={{ flex: 1 }}>
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
      </SafeAreaView>
    );
  }

  // Form step
  return (
    <SafeAreaView edges={SCREEN_EDGES} style={{ flex: 1 }}>
      <ScrollView style={styles.container} contentContainerStyle={[styles.formContent, { paddingBottom }]}>
      {imageUrl && (
        <Image source={{ uri: resolveImageUrl(imageUrl, BASE_URL) ?? undefined }} style={styles.formImage} />
      )}

      <Text style={styles.label}>Name *</Text>
      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder="e.g. Blue Denim Jacket"
      />

      <Text style={styles.label}>Category</Text>
      {renderChips(CATEGORIES, category, (v) => {
        setCategory(v);
        const opts = SUBCATEGORY_OPTIONS[v];
        if (!opts) setSubcategory("none");
        else if (!opts.includes(subcategory)) setSubcategory("none");
      }, needsReview.category)}

      {SUBCATEGORY_OPTIONS[category] && (
        <>
          <Text style={styles.label}>Subcategory</Text>
          {renderChips(SUBCATEGORY_OPTIONS[category]!, subcategory, setSubcategory, needsReview.subcategory)}
        </>
      )}

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

      <Text style={styles.label}>Formality</Text>
      {renderChips(["none", "loungewear", "casual", "smart casual", "dressy", "formal"], formality, setFormality, false)}

      <TouchableOpacity
        style={styles.moreToggle}
        onPress={() => setShowMore(!showMore)}
      >
        <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
          <Text style={styles.moreToggleText}>
            {showMore ? "Less details" : "More details"}
          </Text>
          {showMore ? (
            <ChevronUp size={18} color="#666" strokeWidth={1.5} />
          ) : (
            <ChevronDown size={18} color="#666" strokeWidth={1.5} />
          )}
        </View>
      </TouchableOpacity>

      {showMore && (
        <View style={styles.moreSection}>
          <Text style={styles.label}>Fabric Type</Text>
          {renderChips(FABRIC_TYPES, fabricType, setFabricType, needsReview.fabric_type)}

          <Text style={styles.label}>Fit Type</Text>
          {renderChips(FIT_TYPES, fitType, setFitType, needsReview.fit_type)}

          <Text style={styles.label}>Sleeve Length</Text>
          {renderChips(SLEEVE_LENGTHS, sleeveLength, setSleeveLength, needsReview.sleeve_length)}

          <Text style={styles.label}>Garment Length</Text>
          {renderChips(GARMENT_LENGTHS, garmentLength, setGarmentLength, needsReview.garment_length)}

          <Text style={styles.label}>Embellishments</Text>
          {renderMultiChips(EMBELLISHMENTS, embellishments, (v) => {
            if (v === "none") {
              setEmbellishments(["none"]);
            } else {
              setEmbellishments(prev => {
                const withoutNone = prev.filter(x => x !== "none");
                return withoutNone.includes(v)
                  ? withoutNone.filter(x => x !== v)
                  : [...withoutNone, v];
              });
            }
          }, needsReview.embellishments)}

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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  pickContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl + spacing.sm },
  heading: { fontSize: fontSize.xxl, fontWeight: fontWeight.bold, marginBottom: spacing.sm },
  subtitle: { fontSize: fontSize.sm + 1, color: "#666", textAlign: "center", marginBottom: spacing.xxl, lineHeight: 22 },
  loadingContent: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl + spacing.sm },
  loadingText: { fontSize: fontSize.base, color: "#666", marginTop: spacing.md },
  errorTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.bold, color: colors.danger, marginTop: spacing.lg, marginBottom: spacing.sm },
  errorDetail: { fontSize: fontSize.sm, color: colors.text.tertiary, textAlign: "center", marginBottom: spacing.xl },
  button: {
    width: "100%",
    backgroundColor: colors.accent,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
  },
  buttonText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  formImage: { width: "100%", height: 200, borderRadius: br.md, marginBottom: spacing.lg },
  formContent: { padding: spacing.xl, paddingBottom: spacing.xxl + spacing.sm },
  label: { fontSize: fontSize.sm, fontWeight: fontWeight.semibold, marginTop: spacing.lg, marginBottom: spacing.xs + 2, color: colors.text.primary },
  input: {
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.sm + 6,
    fontSize: fontSize.base,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputReview: {
    borderColor: "#e8b830",
    borderWidth: 2,
    backgroundColor: "#fffef5",
  },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chipRowReview: {
    borderWidth: 2,
    borderColor: "#e8b830",
    borderRadius: br.md,
    paddingVertical: spacing.xs,
    paddingHorizontal: spacing.xs + 2,
    backgroundColor: "#fffef5",
  },
  chip: { paddingHorizontal: spacing.lg, paddingVertical: spacing.sm, borderRadius: 20, backgroundColor: "#e0e0e0" },
  chipActive: { backgroundColor: colors.accent },
  chipText: { fontSize: fontSize.sm, color: "#555", textTransform: "capitalize" },
  chipTextActive: { color: colors.text.white },
  formActions: { marginTop: spacing.xl + 6, gap: spacing.md },
  moreToggle: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing.xl,
    paddingVertical: spacing.sm + 2,
  },
  moreToggleText: { fontSize: fontSize.sm + 1, fontWeight: fontWeight.semibold, color: "#555" },
  moreToggleChevron: { fontSize: fontSize.xs, color: "#555" },
  moreSection: {
    marginTop: spacing.xs,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  saveButton: { backgroundColor: colors.accent, borderRadius: br.md, padding: spacing.lg, alignItems: "center" },
  saveButtonText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  cancelButton: { alignItems: "center", padding: spacing.md },
  cancelButtonText: { color: colors.text.tertiary, fontSize: fontSize.sm + 1 },
});
