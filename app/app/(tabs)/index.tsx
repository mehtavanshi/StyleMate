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
import AsyncStorage from "@react-native-async-storage/async-storage";
import { router } from "expo-router";

import { ConsentStatus, DEMO_USER_ID, consentApi } from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";

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
    <View style={styles.container}>
      <Text style={styles.title}>StyleMate</Text>
      <Text style={styles.subtitle}>Your AI Wardrobe Assistant</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>Quick Stats</Text>
        <Text style={styles.cardText}>
          Open the Wardrobe tab to start adding items.
        </Text>
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

      <View style={styles.divider} />

      <Text style={styles.sectionLabel}>Privacy</Text>

      {consentStatus?.photo_consent ? (
        <TouchableOpacity
          style={styles.linkButton}
          onPress={() => router.push("/consent")}
        >
          <Text style={styles.linkButtonText}>Review consent</Text>
        </TouchableOpacity>
      ) : (
        <TouchableOpacity
          style={[styles.linkButton, styles.linkButtonPrimary]}
          onPress={() => router.push("/consent")}
        >
          <Text style={styles.linkButtonTextPrimary}>Give photo consent</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => router.push("/privacy")}
      >
        <Text style={styles.linkButtonText}>Privacy policy</Text>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => router.push("/settings")}
      >
        <Text style={styles.linkButtonText}>Settings</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, alignItems: "center", justifyContent: "center", padding: 20, backgroundColor: "#f5f5f5" },
  title: { fontSize: 32, fontWeight: "800", marginBottom: 4 },
  subtitle: { fontSize: 16, color: "#666", marginBottom: 30 },
  card: { backgroundColor: "#fff", borderRadius: 12, padding: 20, width: "100%", shadowColor: "#000", shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.1, shadowRadius: 4, elevation: 2 },
  cardTitle: { fontSize: 18, fontWeight: "600", marginBottom: 8 },
  cardText: { fontSize: 14, color: "#555", lineHeight: 20 },
  cta: {
    marginTop: 24,
    backgroundColor: "#333",
    borderRadius: 12,
    paddingVertical: 16,
    paddingHorizontal: 32,
    width: "100%",
    alignItems: "center",
  },
  ctaText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  divider: { height: 1, backgroundColor: "#ddd", width: "100%", marginVertical: 20 },
  sectionLabel: { fontSize: 13, fontWeight: "700", color: "#999", textTransform: "uppercase", letterSpacing: 1, alignSelf: "flex-start", marginBottom: 10 },
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
