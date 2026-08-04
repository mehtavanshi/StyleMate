import { useState } from "react";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";

import { useAuth } from "../lib/auth";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../theme/tokens";

const PASSWORD_MIN_LENGTH = 8;

export default function RegisterScreen() {
  const { signUp } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const passwordValid =
    password.length >= PASSWORD_MIN_LENGTH &&
    /[A-Z]/.test(password) &&
    /\d/.test(password);

  const canSubmit = email.trim().length > 0 && passwordValid && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await signUp(email.trim(), password, name.trim() || undefined);
      router.replace("/(tabs)");
    } catch (e: any) {
      const message = e?.message || "";
      console.log("Registration error:", message, e);
      let friendly = "Could not create your account. Please try again.";
      if (message.includes("409")) {
        friendly = "An account with this email already exists. Sign in instead.";
      } else if (message.includes("422")) {
        friendly = "Please check the email and password requirements.";
      } else if (message.includes("400")) {
        friendly = "Invalid request. Please check your input.";
      } else if (message.includes("500")) {
        friendly = "Server error. Please try again later.";
      } else if (message.includes("Network error") || message.includes("fetch") || message.includes("Failed to fetch")) {
        friendly = "Cannot connect to server. Please check your internet connection.";
      } else if (message && message !== "") {
        friendly = `Registration failed: ${message}`;
      } else {
        friendly = `Registration failed (unknown error): ${JSON.stringify(e)}`;
      }
      setError(friendly);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <ScrollView
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.header}>
            <Text style={styles.title} accessibilityRole="header">
              Create your account
            </Text>
            <Text style={styles.subtitle}>Your AI wardrobe starts here</Text>
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Name (optional)</Text>
            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="How should we call you?"
              placeholderTextColor={colors.text.muted}
              autoComplete="name"
              textContentType="name"
              accessibilityLabel="Name"
              editable={!submitting}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="you@example.com"
              placeholderTextColor={colors.text.muted}
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="emailAddress"
              accessibilityLabel="Email"
              editable={!submitting}
            />
          </View>

          <View style={styles.field}>
            <Text style={styles.label}>Password</Text>
            <View style={styles.passwordRow}>
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                placeholder="At least 8 characters"
                placeholderTextColor={colors.text.muted}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoComplete="new-password"
                textContentType="newPassword"
                accessibilityLabel="Password"
                editable={!submitting}
              />
              <TouchableOpacity
                style={styles.visibilityBtn}
                onPress={() => setShowPassword((v) => !v)}
                accessibilityRole="button"
                accessibilityLabel={showPassword ? "Hide password" : "Show password"}
                accessibilityState={{ disabled: submitting }}
              >
                <Text style={styles.visibilityText}>{showPassword ? "Hide" : "Show"}</Text>
              </TouchableOpacity>
            </View>
            <Text style={styles.hint}>
              Use at least {PASSWORD_MIN_LENGTH} characters, one uppercase letter and one
              number.
            </Text>
          </View>

          {error && (
            <Text style={styles.error} accessibilityRole="alert">
              {error}
            </Text>
          )}

          <TouchableOpacity
            style={[styles.submitButton, !canSubmit && styles.submitDisabled]}
            onPress={handleSubmit}
            disabled={!canSubmit}
            accessibilityRole="button"
            accessibilityLabel="Create account"
            accessibilityState={{ disabled: !canSubmit, busy: submitting }}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.submitText}>Create Account</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.switchRow}
            onPress={() => router.replace("/login")}
            accessibilityRole="button"
            accessibilityLabel="Go to sign in"
          >
            <Text style={styles.switchText}>
              Already have an account?{" "}
              <Text style={styles.switchLink}>Sign in</Text>
            </Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  flex: { flex: 1 },
  content: { flexGrow: 1, padding: spacing.xl, justifyContent: "center" },
  header: { marginBottom: spacing.xxl },
  title: { fontSize: fontSize.xxl, fontWeight: fontWeight.extrabold, color: colors.accent },
  subtitle: { fontSize: fontSize.base, color: colors.text.secondary, marginTop: spacing.xs },
  field: { marginBottom: spacing.lg },
  label: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 1,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surface,
    borderRadius: br.md,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md + 2,
    fontSize: fontSize.base,
    color: colors.text.primary,
  },
  passwordRow: { position: "relative" },
  visibilityBtn: {
    position: "absolute",
    right: spacing.lg,
    top: 0,
    bottom: 0,
    justifyContent: "center",
  },
  visibilityText: {
    fontSize: fontSize.sm,
    fontWeight: fontWeight.semibold,
    color: colors.accent,
  },
  hint: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },
  error: { color: colors.danger, fontSize: fontSize.sm, marginBottom: spacing.md },
  submitButton: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  submitDisabled: { opacity: 0.5 },
  submitText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  switchRow: { alignItems: "center", marginTop: spacing.xl },
  switchText: { fontSize: fontSize.sm, color: colors.text.secondary },
  switchLink: { color: colors.accent, fontWeight: fontWeight.semibold },
});
