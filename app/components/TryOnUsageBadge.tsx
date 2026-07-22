import { useCallback, useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { DEMO_USER_ID, tryOnApi, TryOnUsage } from "../lib/api";

export default function TryOnUsageBadge() {
  const [usage, setUsage] = useState<TryOnUsage | null>(null);

  const fetchUsage = useCallback(async () => {
    try {
      const data = await tryOnApi.usage(DEMO_USER_ID);
      setUsage(data);
    } catch {
      // Silently fail — badge just won't show
    }
  }, []);

  useEffect(() => {
    fetchUsage();
  }, [fetchUsage]);

  if (!usage) return null;

  const isAtLimit = usage.remaining <= 0;

  return (
    <View
      style={[styles.badge, isAtLimit && styles.badgeAtLimit]}
      accessibilityRole="text"
      accessibilityLabel={
        isAtLimit
          ? `Daily try-on limit reached. Resets at ${new Date(usage.resets_at).toLocaleTimeString()}`
          : `${usage.remaining} of ${usage.limit} try-ons left today`
      }
    >
      <Text style={[styles.badgeText, isAtLimit && styles.badgeTextAtLimit]}>
        {isAtLimit
          ? `Resets at ${new Date(usage.resets_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
          : `${usage.remaining} of ${usage.limit} try-ons left today`}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    backgroundColor: "#f0f0f0",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 6,
    alignSelf: "center",
    marginTop: 12,
  },
  badgeAtLimit: {
    backgroundColor: "#FFF0E0",
  },
  badgeText: {
    fontSize: 13,
    color: "#666",
    fontWeight: "500",
  },
  badgeTextAtLimit: {
    color: "#B8860B",
  },
});
