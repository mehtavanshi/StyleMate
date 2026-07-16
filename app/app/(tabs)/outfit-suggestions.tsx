import { StyleSheet, Text, View } from "react-native";

export default function OutfitSuggestionsScreen() {
  return (
    <View style={styles.container}>
      <View style={styles.center}>
        <Text style={styles.emptyTitle}>Outfit Suggestions</Text>
        <Text style={styles.emptyText}>
          AI-powered outfit pairing coming soon.{"\n\n"}
          Add clothing items to your wardrobe first, then this screen will suggest
          complete outfits based on occasion, season, and color harmony.
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30 },
  emptyTitle: { fontSize: 20, fontWeight: "700", marginBottom: 10 },
  emptyText: { fontSize: 14, color: "#888", textAlign: "center", lineHeight: 22 },
});
