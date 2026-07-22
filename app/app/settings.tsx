import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../theme/tokens";
import { router, useNavigation } from "expo-router";

import { BASE_URL } from "../config/api";
import { ConsentStatus, DEMO_USER_ID, consentApi } from "../lib/api";
import { resolvePhotoUrl } from "../lib/constants";

export default function SettingsScreen() {
  const navigation = useNavigation();
  const [consentStatus, setConsentStatus] = useState<ConsentStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    navigation.setOptions({ title: "Settings", headerShown: true });
  }, [navigation]);

  const fetchStatus = useCallback(async () => {
    try {
      const s = await consentApi.getStatus(DEMO_USER_ID);
      setConsentStatus(s);
    } catch {
      //
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

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
                prev ? { ...prev, photo_url: null } : null,
              );
            } catch {
              Alert.alert("Error", "Could not delete photo. Please try again.");
            }
          },
        },
      ],
    );
  };

  if (loading) {
    return (
      <View style={styles.centered} accessibilityRole="progressbar" accessibilityLabel="Loading settings">
        <ActivityIndicator size="large" color="#333" />
      </View>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.heading}>Settings</Text>

      {/* ── My Photo section ── */}
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
        </>
      ) : (
        <TouchableOpacity
          style={[styles.linkButton, styles.linkButtonPrimary]}
          onPress={() => router.push("/consent")}
        >
          <Text style={styles.linkButtonTextPrimary}>Give photo consent first</Text>
        </TouchableOpacity>
      )}

      {/* ── Privacy section ── */}
      <View style={styles.sectionSpacer} />
      <Text style={styles.sectionLabel}>Privacy</Text>

      {consentStatus?.photo_consent && consentStatus?.photo_url && (
        <TouchableOpacity
          style={[styles.linkButton, styles.deleteButton]}
          onPress={handleDeletePhoto}
        >
          <Text style={styles.deleteButtonText}>Delete my photo</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => router.push("/consent")}
      >
        <Text style={styles.linkButtonText}>
          {consentStatus?.photo_consent
            ? "Review consent"
            : "Give photo consent"}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => router.push("/privacy")}
      >
        <Text style={styles.linkButtonText}>Privacy policy</Text>
      </TouchableOpacity>
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xxl + spacing.sm },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
  },
  heading: { fontSize: fontSize.xxl + 2, fontWeight: fontWeight.extrabold, marginBottom: spacing.xl },
  sectionLabel: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: spacing.sm,
  },
  sectionSpacer: { height: spacing.xl },
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
