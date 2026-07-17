import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  Linking,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { useLocalSearchParams, useNavigation } from "expo-router";
import * as LinkingExpo from "expo-linking";
import {
  styleMatchApi,
  StyleMatchItem,
  StyleMatchResponse,
  ShoppingSuggestion,
  OccasionOutfit,
} from "./lib/api";
import { BASE_URL } from "./config/api";

export default function StyleMatchScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const [data, setData] = useState<StyleMatchResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    navigation.setOptions({ title: "Style Match", headerShown: true });
  }, [navigation]);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await styleMatchApi.get(Number(id));
        setData(res);
      } catch (e: any) {
        Alert.alert("Error", e.message);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Finding your perfect matches…</Text>
      </View>
    );
  }

  if (!data) {
    return (
      <View style={styles.center}>
        <Text style={styles.loadingText}>No matches found.</Text>
      </View>
    );
  }

  const openLink = async (url: string) => {
    try {
      const supported = await LinkingExpo.canOpenURL(url);
      if (supported) await LinkingExpo.openURL(url);
      else Alert.alert("Can't open link", url);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  const selected = data.selectedItem;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Selected item hero */}
      <View style={styles.hero}>
        {selected.image_url ? (
          <Image
            source={{ uri: `${BASE_URL}${selected.image_url}` }}
            style={styles.heroImage}
          />
        ) : (
          <View style={[styles.heroImage, styles.heroPlaceholder]}>
            <Text style={styles.heroInitial}>
              {(selected.name || "?")[0]?.toUpperCase()}
            </Text>
          </View>
        )}
        <Text style={styles.heroName}>{selected.name}</Text>
        <Text style={styles.heroSub}>
          {[selected.color, selected.category, selected.occasion_tag]
            .filter(Boolean)
            .map((s) => (s || "").toString())
            .join(" • ")}
        </Text>
      </View>

      {/* Already in your wardrobe */}
      <Section title="🏠 Already In Your Wardrobe">
        {data.alreadyOwned.length === 0 ? (
          <Empty text="Nothing else in your wardrobe pairs with this yet." />
        ) : (
          data.alreadyOwned.map((it, i) => (
            <MatchCard key={`own-${i}`} item={it} onPress={() => {}} />
          ))
        )}
      </Section>

      {/* Matching bottoms */}
      <MatchSection title="👖 Matching Bottoms" items={data.matchingBottoms} />

      {/* Matching tops */}
      <MatchSection title="👚 Matching Tops" items={data.matchingTops} />

      {/* Footwear */}
      <MatchSection title="👟 Footwear" items={data.matchingFootwear} />

      {/* Accessories */}
      <MatchSection title="⌚ Accessories" items={data.matchingAccessories} />

      {/* Layering */}
      <MatchSection title="🧥 Layering" items={data.layeringSuggestions} />

      {/* Best color pairings */}
      <ColorSection title="🎨 Best Color Pairings" colors={data.recommendedColors} good />

      {/* Avoid colors */}
      <ColorSection title="❌ Avoid These Colors" colors={data.avoidColors} good={false} />

      {/* Outfit ideas */}
      <Section title="✨ Outfit Ideas">
        <View style={styles.chipRow}>
          {data.occasionOutfits.map((o: OccasionOutfit, i) => (
            <View key={`occ-${i}`} style={styles.occasionChip}>
              <Text style={styles.occasionChipText}>{o.name}</Text>
            </View>
          ))}
        </View>
      </Section>

      {/* Shop matching items */}
      <Section title="🛍 Shop Matching Items">
        {data.shoppingSuggestions.map((s: ShoppingSuggestion, i) => (
          <View key={`shop-${i}`} style={styles.shopBlock}>
            <View style={styles.shopHead}>
              <Text style={styles.shopName}>{s.item_name}</Text>
              <Text style={styles.shopPct}>{s.match_percentage}% match</Text>
            </View>
            <Text style={styles.shopReason}>{s.reason}</Text>
            <View style={styles.storeRow}>
              {s.shopping_links.map((l, j) => (
                <TouchableOpacity
                  key={`${l.store}-${j}`}
                  style={styles.storeBtn}
                  onPress={() => openLink(l.url)}
                >
                  <Text style={styles.storeBtnText}>
                    {l.store.charAt(0).toUpperCase() + l.store.slice(1)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>
        ))}
      </Section>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

function MatchSection({ title, items }: { title: string; items: StyleMatchItem[] }) {
  if (!items || items.length === 0) return null;
  return (
    <Section title={title}>
      {items.map((it, i) => (
        <MatchCard key={`${title}-${i}`} item={it} />
      ))}
    </Section>
  );
}

function MatchCard({ item, onPress }: { item: StyleMatchItem; onPress?: () => void }) {
  const scoreColor =
    item.match_percentage >= 85
      ? "#2ECC71"
      : item.match_percentage >= 70
      ? "#E8A317"
      : "#E74C3C";
  return (
    <TouchableOpacity style={styles.matchCard} activeOpacity={0.9} onPress={onPress}>
      <View style={styles.matchInfo}>
        <View style={styles.matchNameRow}>
          <Text style={styles.matchName}>{item.name}</Text>
          {item.owned && <View style={styles.ownedBadge}>
            <Text style={styles.ownedBadgeText}>OWNED</Text>
          </View>}
        </View>
        <Text style={styles.matchReason}>{item.reason}</Text>
      </View>
      <View style={[styles.scoreBadge, { backgroundColor: scoreColor + "22" }]}>
        <Text style={[styles.scoreText, { color: scoreColor }]}>
          {item.match_percentage}%
        </Text>
      </View>
    </TouchableOpacity>
  );
}

function ColorSection({
  title,
  colors,
  good,
}: {
  title: string;
  colors: string[];
  good: boolean;
}) {
  if (!colors || colors.length === 0) return null;
  return (
    <Section title={title}>
      <View style={styles.chipRow}>
        {colors.map((c, i) => (
          <View
            key={`col-${i}`}
            style={[
              styles.colorChip,
              { borderColor: good ? "#2ECC71" : "#E74C3C" },
            ]}
          >
            <Text style={styles.colorChipText}>{c}</Text>
          </View>
        ))}
      </View>
    </Section>
  );
}

function Empty({ text }: { text: string }) {
  return <Text style={styles.empty}>{text}</Text>;
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30 },
  loadingText: { fontSize: 14, color: "#888", marginTop: 10, textAlign: "center" },

  hero: { alignItems: "center", padding: 20, backgroundColor: "#fff" },
  heroImage: { width: 140, height: 140, borderRadius: 16, backgroundColor: "#e0e0e0" },
  heroPlaceholder: { alignItems: "center", justifyContent: "center" },
  heroInitial: { fontSize: 48, fontWeight: "800", color: "#999" },
  heroName: { fontSize: 20, fontWeight: "800", marginTop: 12 },
  heroSub: { fontSize: 13, color: "#888", marginTop: 4, textTransform: "capitalize" },

  section: {
    marginTop: 10,
    backgroundColor: "#fff",
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  sectionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 10 },

  matchCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fafafa",
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: "#eee",
  },
  matchInfo: { flex: 1, marginRight: 10 },
  matchNameRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  matchName: { fontSize: 14, fontWeight: "700", color: "#222" },
  matchReason: { fontSize: 12, color: "#777", marginTop: 2 },
  ownedBadge: {
    backgroundColor: "#2ECC7122",
    borderRadius: 6,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  ownedBadgeText: { fontSize: 9, fontWeight: "800", color: "#2ECC71" },
  scoreBadge: { borderRadius: 10, paddingHorizontal: 10, paddingVertical: 6 },
  scoreText: { fontSize: 14, fontWeight: "800" },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  colorChip: {
    borderRadius: 16,
    borderWidth: 1.5,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: "#fff",
  },
  colorChipText: { fontSize: 12, fontWeight: "600", color: "#333" },

  occasionChip: {
    backgroundColor: "#333",
    borderRadius: 16,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  occasionChipText: { fontSize: 13, fontWeight: "600", color: "#fff" },

  empty: { fontSize: 13, color: "#aaa", fontStyle: "italic" },

  shopBlock: {
    backgroundColor: "#fafafa",
    borderRadius: 12,
    padding: 12,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: "#eee",
  },
  shopHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  shopName: { fontSize: 14, fontWeight: "700", color: "#222" },
  shopPct: { fontSize: 12, fontWeight: "700", color: "#2ECC71" },
  shopReason: { fontSize: 12, color: "#777", marginTop: 4, marginBottom: 10 },
  storeRow: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  storeBtn: {
    backgroundColor: "#333",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  storeBtnText: { fontSize: 12, fontWeight: "600", color: "#fff" },
});
