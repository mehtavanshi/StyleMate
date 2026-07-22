import { StyleSheet, View, Text } from "react-native";
import Svg, { Path } from "react-native-svg";

export default function SilhouetteOverlay() {
  return (
    <View style={styles.overlay} pointerEvents="none">
      <View style={styles.outlineContainer}>
        <Svg width="100%" height="100%" viewBox="0 0 200 500">
          <Path
            d="
              M 100 20
              C 100 20, 85 15, 70 25
              C 55 35, 50 50, 50 50
              L 50 40
              C 50 30, 40 25, 35 35
              C 30 45, 35 55, 40 60
              L 40 80
              C 40 85, 35 85, 30 90
              L 30 110
              C 30 115, 25 115, 20 120
              L 20 140
              C 20 150, 30 155, 40 155
              L 40 170
              C 40 175, 35 180, 30 190
              L 30 220
              C 30 230, 20 235, 15 240
              L 15 260
              C 15 270, 25 275, 35 275
              L 35 350
              C 35 370, 40 380, 50 390
              L 50 470
              C 50 480, 60 490, 70 490
              L 130 490
              C 140 490, 150 480, 150 470
              L 150 390
              C 160 380, 165 370, 165 350
              L 165 275
              C 175 275, 185 270, 185 260
              L 185 240
              C 185 235, 175 230, 170 220
              L 170 190
              C 170 180, 165 175, 160 170
              L 160 155
              C 170 155, 180 150, 180 140
              L 180 120
              C 180 115, 175 115, 170 110
              L 170 90
              C 170 85, 165 85, 160 80
              L 160 60
              C 165 55, 170 45, 165 35
              C 160 25, 150 30, 150 40
              L 150 50
              C 150 50, 145 35, 130 25
              C 115 15, 100 20, 100 20
              Z
            "
            fill="none"
            stroke="rgba(255,255,255,0.6)"
            strokeWidth="3"
            strokeDasharray="6,4"
          />
        </Svg>
      </View>
      <Text style={styles.hint}>Stand inside the outline</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    justifyContent: "center",
  },
  outlineContainer: {
    width: "50%",
    height: "75%",
    alignItems: "center",
    justifyContent: "center",
  },
  hint: {
    position: "absolute",
    bottom: 60,
    fontSize: 14,
    color: "rgba(255,255,255,0.8)",
    backgroundColor: "rgba(0,0,0,0.4)",
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 20,
    overflow: "hidden",
  },
});
