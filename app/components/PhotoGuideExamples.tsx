import { Image, StyleSheet, Text, View } from "react-native";

export default function PhotoGuideExamples() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Photo tips</Text>
      <View style={styles.row}>
        <View style={styles.example}>
          <View style={[styles.imageWrap, styles.goodBorder]}>
            <View style={styles.placeholderGood}>
              <Text style={styles.placeholderIcon}>{"\u2713"}</Text>
            </View>
          </View>
          <Text style={styles.labelGood}>Do this</Text>
          <Text style={styles.desc}>
            Standing straight, plain background, good lighting
          </Text>
        </View>

        <View style={styles.example}>
          <View style={[styles.imageWrap, styles.badBorder]}>
            <View style={styles.placeholderBad}>
              <Text style={styles.placeholderIcon}>{"\u2717"}</Text>
            </View>
          </View>
          <Text style={styles.labelBad}>Avoid</Text>
          <Text style={styles.desc}>
            Cropped, sitting, cluttered background
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 20,
    paddingVertical: 12,
    backgroundColor: "#f5f5f5",
  },
  title: {
    fontSize: 14,
    fontWeight: "700",
    color: "#555",
    marginBottom: 8,
    textAlign: "center",
  },
  row: {
    flexDirection: "row",
    gap: 12,
  },
  example: {
    flex: 1,
    alignItems: "center",
  },
  imageWrap: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: 10,
    borderWidth: 2,
    overflow: "hidden",
    marginBottom: 6,
  },
  goodBorder: { borderColor: "#2a7" },
  badBorder: { borderColor: "#c44" },
  placeholderGood: {
    flex: 1,
    backgroundColor: "#e8f8e8",
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderBad: {
    flex: 1,
    backgroundColor: "#fce8e8",
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderIcon: { fontSize: 28, fontWeight: "700" },
  labelGood: { fontSize: 13, fontWeight: "700", color: "#2a7", marginBottom: 2 },
  labelBad: { fontSize: 13, fontWeight: "700", color: "#c44", marginBottom: 2 },
  desc: { fontSize: 11, color: "#888", textAlign: "center", lineHeight: 15 },
});
