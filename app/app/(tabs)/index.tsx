import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, shadow, spacing } from "../../theme/tokens";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

import { ConsentStatus, DEMO_USER_ID, consentApi } from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";
import TryOnUsageBadge from "../../components/TryOnUsageBadge";

const ONBOARDING_FLAG = "onboarding_complete";

export default function HomeScreen() {
  const [checked, setChecked] = useState(false);
  const [seen, setSeen] = useState(false);
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);

  useEffect(() => {
    AsyncStorage.getItem(ONBOARDING_FLAG)
      .then((v) => setSeen(!!v))
      .finally(() => setChecked(true));
  }, []);

  useEffect(() => {
    consentApi
      .getStatus(DEMO_USER_ID)
      .then((s) => setConsentStatus(s))
      .catch(() => {});
  }, []);

  const handleDeletePhoto = () => {
    Alert.alert(
      "Delete my photo",
      "This can't be undone. You'll need to upload a new photo to use Try It On.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              await consentApi.deletePhoto(DEMO_USER_ID);
              setConsentStatus((prev) =>
                prev ? { ...prev, photo_url: null } : null
              );
            } catch {
              Alert.alert("Error", "Could not delete photo. Please try again.");
            }
          },
        },
      ],
    );
  };

  return (
    <SafeAreaView style={styles.container} accessibilityRole="none">
      <Text style={styles.title} accessibilityRole="header">StyleMate</Text>
      <Text style={styles.subtitle}>Your AI Wardrobe Assistant</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Quick Stats</Text>
        <Text style={styles.cardText}>
          Open the Wardrobe tab to start adding items.
        </Text>
        <TryOnUsageBadge />
      </View>

      {!checked ? (
        <ActivityIndicator style={{ marginTop: 20 }} color="#333" />
      ) : !seen ? (
        <TouchableOpacity
          style={styles.cta}
          onPress={() => router.push("/onboarding")}
        >
          <Text style={styles.ctaText}>Tell us your shape</Text>
        </TouchableOpacity>
      ) : null}

      <View style={styles.divider} />

      <Text style={styles.sectionLabel}>My Photo</Text>

      {consentStatus?.photo_consent ? (
        <>
          {consentStatus?.photo_url && (
            <View style={styles.photoPreviewWrap}>
              <Image
                source={{ uri: resolvePhotoUrl(consentStatus.photo_url, BASE_URL) ?? undefined }}
                style={styles.photoPreview}
                resizeMode="cover"
              />
            </View>
          )}
          <TouchableOpacity
            style={styles.linkButton}
            onPress={() => router.push("/capture")}
          >
            <Text style={styles.linkButtonText}>
              {consentStatus?.photo_url ? "Update my photo" : "Take my photo"}
            </Text>
          </TouchableOpacity>
          {consentStatus?.photo_url && (
            <TouchableOpacity
              style={[styles.linkButton, styles.deleteButton]}
              onPress={handleDeletePhoto}
            >
              <Text style={styles.deleteButtonText}>Delete my photo</Text>
            </TouchableOpacity>
          )}
        </>
      ) : (
        <TouchableOpacity
          style={[styles.linkButton, styles.linkButtonPrimary]}
          onPress={() => router.push("/consent")}
        >
          <Text style={styles.linkButtonTextPrimary}>Give photo consent first</Text>
        </TouchableOpacity>
      )}


    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl, backgroundColor: colors.background },
  title: { fontSize: fontSize.xxxl, fontWeight: fontWeight.extrabold, marginBottom: spacing.xs },
  subtitle: { fontSize: fontSize.base, color: "#666", marginBottom: spacing.xxl - 2 },
  card: { backgroundColor: colors.surface, borderRadius: br.md, padding: spacing.xl, width: "100%", ...shadow.sm },
  cardTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.semibold, marginBottom: spacing.sm },
  cardText: { fontSize: fontSize.sm, color: "#555", lineHeight: 20 },
  cta: {
    marginTop: spacing.xl,
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.xxl,
    width: "100%",
    alignItems: "center",
  },
  ctaText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  divider: { height: 1, backgroundColor: "#ddd", width: "100%", marginVertical: spacing.xl },
  sectionLabel: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold, color: colors.text.light, textTransform: "uppercase", letterSpacing: 1, alignSelf: "flex-start", marginBottom: spacing.sm },
  photoPreviewWrap: {
    width: "100%",
    marginBottom: spacing.sm,
    borderRadius: br.md,
    overflow: "hidden",
    backgroundColor: "#e0e0e0",
  },
  photoPreview: {
    width: "100%",
    height: 200,
  },

  linkButton: {
    width: "100%",
    backgroundColor: colors.surface,
    borderRadius: br.md,
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e0e0e0",
  },
  linkButtonPrimary: { backgroundColor: colors.accent, borderColor: colors.accent },
  linkButtonText: { fontSize: fontSize.sm + 1, color: colors.accent, fontWeight: fontWeight.semibold },
  linkButtonTextPrimary: { fontSize: fontSize.sm + 1, color: colors.text.white, fontWeight: fontWeight.bold },
  deleteButton: { borderColor: "#c00" },
  deleteButtonText: { fontSize: fontSize.sm + 1, color: "#c00", fontWeight: fontWeight.semibold },
});
