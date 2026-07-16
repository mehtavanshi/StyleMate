import { StyleSheet, Text, View } from "react-native";

export default function HomeScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>StyleMate</Text>
      <Text style={styles.subtitle}>Your AI Wardrobe Assistant</Text>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Quick Stats</Text>
        <Text style={styles.cardText}>Open the Wardrobe tab to start adding items.</Text>
      </View>
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
});
