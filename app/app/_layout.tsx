import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth } from "../lib/auth";
import { colors } from "../theme/tokens";

function RootNavigator() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <View
        style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background }}
        accessibilityRole="progressbar"
        accessibilityLabel="Loading your session"
      >
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="capsule" />
        <Stack.Screen name="capture" />
        <Stack.Screen name="consent" />
        <Stack.Screen name="onboarding" />
        <Stack.Screen name="packing" />
        <Stack.Screen name="privacy" />
        <Stack.Screen name="settings" />
        <Stack.Screen name="style-match" />
        <Stack.Screen name="style-rating" />
        <Stack.Screen name="try-on" />
        <Stack.Screen name="wardrobe/[id]" />
      </Stack.Protected>

      <Stack.Protected guard={!user}>
        <Stack.Screen name="login" />
        <Stack.Screen name="register" />
      </Stack.Protected>
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <AuthProvider>
      <SafeAreaProvider>
        <StatusBar style="dark" translucent={false} />
        <RootNavigator />
      </SafeAreaProvider>
    </AuthProvider>
  );
}
