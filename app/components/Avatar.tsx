import { useState } from "react";
import { Image, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { resolvePhotoUrl } from "../lib/constants";
import { BASE_URL } from "../config/api";
import { colors, fontWeight } from "../theme/tokens";

interface AvatarProps {
  photoUrl?: string | null;
  name?: string | null;
  size?: number;
  onPress?: () => void;
}

export default function Avatar({ photoUrl, name, size = 44, onPress }: AvatarProps) {
  const [imgFailed, setImgFailed] = useState(false);
  const uri = resolvePhotoUrl(photoUrl ?? null, BASE_URL);
  const initial = (name || "?")[0]?.toUpperCase() || "?";

  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={!onPress}
      accessibilityLabel="Profile photo – tap to change"
      activeOpacity={onPress ? 0.7 : 1}
    >
      {uri && !imgFailed ? (
        <Image
          source={{ uri: uri ?? undefined }}
          style={[styles.image, { width: size, height: size, borderRadius: size / 2 }]}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <View
          style={[
            styles.placeholder,
            { width: size, height: size, borderRadius: size / 2 },
          ]}
        >
          <Text style={[styles.initial, { fontSize: size * 0.42 }]}>{initial}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  image: {
    backgroundColor: colors.background,
  },
  placeholder: {
    backgroundColor: "#d0d0d0",
    alignItems: "center",
    justifyContent: "center",
  },
  initial: {
    color: colors.text.light,
    fontWeight: fontWeight.bold,
  },
});
