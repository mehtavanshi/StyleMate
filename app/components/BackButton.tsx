import { useCallback } from "react";
import { StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { useNavigation, router } from "expo-router";
import { ArrowLeft } from "../lib/icons";
import { colors, fontSize, fontWeight, spacing } from "../theme/tokens";

interface BackButtonProps {
  title?: string;
  light?: boolean;
  onPress?: () => void;
}

export default function BackButton({ title, light, onPress }: BackButtonProps) {
  const navigation = useNavigation();

  const handlePress = useCallback(() => {
    if (onPress) {
      onPress();
      return;
    }
    if (navigation.canGoBack()) {
      navigation.goBack();
    } else {
      router.replace("/(tabs)");
    }
  }, [navigation, onPress]);

  const iconColor = light ? "#fff" : colors.accent;

  if (title) {
    return (
      <View style={styles.headerRow}>
        <TouchableOpacity onPress={handlePress} accessibilityLabel="Go back">
          <ArrowLeft size={22} color={iconColor} strokeWidth={1.5} />
        </TouchableOpacity>
        <Text style={[styles.headerTitle, light && styles.headerTitleLight]} accessibilityRole="header">
          {title}
        </Text>
      </View>
    );
  }

  return (
    <TouchableOpacity onPress={handlePress} accessibilityLabel="Go back" style={styles.iconOnly}>
      <ArrowLeft size={22} color={iconColor} strokeWidth={1.5} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  headerTitle: {
    fontSize: fontSize.xl,
    fontWeight: fontWeight.bold,
    color: colors.text.primary,
  },
  headerTitleLight: {
    color: colors.text.white,
  },
  iconOnly: {
    padding: spacing.xs,
  },
});
