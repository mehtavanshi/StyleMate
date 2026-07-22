import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { borderRadius as br, colors, fontSize, fontWeight, shadow, spacing } from "../theme/tokens";
import { router, useNavigation } from "expo-router";

import { consentApi, DEMO_USER_ID } from "../lib/api";

export default function ConsentScreen() {
  const navigation = useNavigation();
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    navigation.setOptions({ title: "Photo Privacy Consent", headerShown: true });
  }, [navigation]);

  const checkExisting = useCallback(async () => {
    try {
      const status = await consentApi.getStatus(DEMO_USER_ID);
      if (status.photo_consent) {
        router.back();
      }
    } catch {
      // server unreachable — let user consent again
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    checkExisting();
  }, [checkExisting]);

  const handleGiveConsent = async () => {
    if (!agreed) return;
    setSubmitting(true);
    try {
      await consentApi.giveConsent(DEMO_USER_ID);
      router.back();
    } catch (e: any) {
      // error handled silently; user can retry
    } finally {
      setSubmitting(false);
    }
  };

  if (checking) {
    return (
      <View style={styles.centered} accessibilityRole="progressbar" accessibilityLabel="Checking consent status">
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
      <Text style={styles.heading}>Your privacy matters</Text>
      <Text style={styles.subtitle}>
        Before you upload any photos, we want you to understand exactly what
        happens with them.
      </Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>What your photo is used for</Text>
        <Text style={styles.bullet}>
          {"\u2713"} Your photo is used only to render clothing on your body
          (virtual try-on).
        </Text>
        <Text style={styles.bullet}>
          {"\u2713"} It is stored securely and you can delete it at any time.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>What your photo is NOT used for</Text>
        <Text style={styles.crossBullet}>
          {"\u2717"} It is NOT used to train AI or machine learning models.
        </Text>
        <Text style={styles.crossBullet}>
          {"\u2717"} It is NOT shared with other users.
        </Text>
        <Text style={styles.crossBullet}>
          {"\u2717"} It is NOT sold or shared with third parties.
        </Text>
      </View>

      <TouchableOpacity
        onPress={() => router.push("/privacy")}
        style={styles.privacyLink}
      >
        <Text style={styles.privacyLinkText}>
          Read our full privacy policy
        </Text>
      </TouchableOpacity>

      <View style={styles.toggleRow}>
        <Switch
          value={agreed}
          onValueChange={setAgreed}
          trackColor={{ false: "#ccc", true: "#333" }}
          thumbColor="#fff"
        />
        <Text style={styles.toggleLabel}>
          I understand and agree to the above.
        </Text>
      </View>

      <TouchableOpacity
        style={[styles.button, (!agreed || submitting) && styles.buttonDisabled]}
        onPress={handleGiveConsent}
        disabled={!agreed || submitting}
      >
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Continue</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, paddingBottom: spacing.xxl + spacing.sm },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background },
  heading: { fontSize: fontSize.xxl, fontWeight: fontWeight.extrabold, marginBottom: spacing.xs + 2 },
  subtitle: { fontSize: fontSize.sm + 1, color: "#666", marginBottom: spacing.xl, lineHeight: 22 },
  card: {
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.lg,
    marginBottom: spacing.sm + 6,
    ...shadow.sm,
  },
  cardTitle: { fontSize: fontSize.base, fontWeight: fontWeight.bold, marginBottom: spacing.sm, color: colors.accent },
  bullet: { fontSize: fontSize.sm, color: "#2a7", marginBottom: spacing.xs + 2, lineHeight: 20 },
  crossBullet: { fontSize: fontSize.sm, color: "#c44", marginBottom: spacing.xs + 2, lineHeight: 20 },
  privacyLink: { alignSelf: "flex-start", marginBottom: spacing.xl },
  privacyLinkText: { fontSize: fontSize.sm, color: "#555", textDecorationLine: "underline" },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: br.md,
    padding: spacing.lg,
    marginBottom: spacing.xl,
    ...shadow.sm,
  },
  toggleLabel: { flex: 1, marginLeft: spacing.sm + 6, fontSize: fontSize.sm + 1, color: colors.accent, lineHeight: 21 },
  button: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
  },
  buttonDisabled: { backgroundColor: colors.text.muted },
  buttonText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
});
