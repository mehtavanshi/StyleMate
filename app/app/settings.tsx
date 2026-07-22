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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 20, paddingBottom: 40 },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f5f5f5",
  },
  heading: { fontSize: 26, fontWeight: "800", marginBottom: 20 },
  sectionLabel: {
    fontSize: 13,
    fontWeight: "700",
    color: "#999",
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: 10,
  },
  sectionSpacer: { height: 24 },
  photoPreviewWrap: {
    width: "100%",
    marginBottom: 10,
    borderRadius: 12,
    overflow: "hidden",
    backgroundColor: "#e0e0e0",
  },
  photoPreview: {
    width: "100%",
    height: 200,
  },
  linkButton: {
    width: "100%",
    backgroundColor: "#fff",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 8,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#e0e0e0",
  },
  linkButtonPrimary: { backgroundColor: "#333", borderColor: "#333" },
  linkButtonText: { fontSize: 15, color: "#333", fontWeight: "600" },
  linkButtonTextPrimary: { fontSize: 15, color: "#fff", fontWeight: "700" },
  deleteButton: { borderColor: "#c00" },
  deleteButtonText: { fontSize: 15, color: "#c00", fontWeight: "600" },
});
