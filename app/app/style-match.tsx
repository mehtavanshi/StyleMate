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
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useNavigation } from "expo-router";
import * as LinkingExpo from "expo-linking";
import {
  styleMatchApi,
  StyleMatchItem,
  StyleMatchResponse,
  ShoppingSuggestion,
  OccasionOutfit,
} from "../lib/api";
import { BASE_URL } from "../config/api";
import {
  House,
  Layers,
  Palette,
  Shirt,
  ShoppingBag,
  Sparkles,
  Watch,
  XCircle,
  type LucideProps,
} from "../lib/icons";
import {
  borderRadius as br,
  colors,
  fontSize,
  fontWeight,
  MIN_TOUCH_TARGET,
  shadow,
  spacing,
} from "../theme/tokens";

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
    <SafeAreaView style={{ flex: 1 }}>
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
      <Section title="Already In Your Wardrobe" icon={House}>
        {data.alreadyOwned.length === 0 ? (
          <Empty text="Nothing else in your wardrobe pairs with this yet." />
        ) : (
          data.alreadyOwned.map((it, i) => (
            <MatchCard key={`own-${i}`} item={it} onPress={() => {}} />
          ))
        )}
      </Section>

      {/* Matching bottoms */}
      <MatchSection title="Matching Bottoms" icon={Shirt} items={data.matchingBottoms} />

      {/* Matching tops */}
      <MatchSection title="Matching Tops" icon={Shirt} items={data.matchingTops} />

      {/* Footwear */}
      <MatchSection title="Footwear" icon={Watch} items={data.matchingFootwear} />

      {/* Accessories */}
      <MatchSection title="Accessories" icon={Watch} items={data.matchingAccessories} />

      {/* Layering */}
      <MatchSection title="Layering" icon={Layers} items={data.layeringSuggestions} />

      {/* Best color pairings */}
      <ColorSection title="Best Color Pairings" icon={Palette} colors={data.recommendedColors} good />

      {/* Avoid colors */}
      <ColorSection title="Avoid These Colors" icon={XCircle} colors={data.avoidColors} good={false} />

      {/* Outfit ideas */}
      <Section title="Outfit Ideas" icon={Sparkles}>
        <View style={styles.chipRow}>
          {data.occasionOutfits.map((o: OccasionOutfit, i) => (
            <View key={`occ-${i}`} style={styles.occasionChip}>
              <Text style={styles.occasionChipText}>{o.name}</Text>
            </View>
          ))}
        </View>
      </Section>

      {/* Shop matching items */}
      <Section title="Shop Matching Items" icon={ShoppingBag}>
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
    </SafeAreaView>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: React.ComponentType<LucideProps>;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>
        {Icon && <Icon size={18} strokeWidth={1.5} color={colors.accent} style={{ marginRight: spacing.xs }} />}
        {title}
      </Text>
      {children}
    </View>
  );
}

function MatchSection({
  title,
  icon,
  items,
}: {
  title: string;
  icon?: React.ComponentType<LucideProps>;
  items: StyleMatchItem[];
}) {
  if (!items || items.length === 0) return null;
  return (
    <Section title={title} icon={icon}>
      {items.map((it, i) => (
        <MatchCard key={`${title}-${i}`} item={it} />
      ))}
    </Section>
  );
}

function MatchCard({ item, onPress }: { item: StyleMatchItem; onPress?: () => void }) {
  const scoreColor =
    item.match_percentage >= 85
      ? colors.score.high
      : item.match_percentage >= 70
      ? colors.score.mid
      : colors.score.low;
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
  colors: colorList,
  good,
  icon,
}: {
  title: string;
  colors: string[];
  good: boolean;
  icon?: React.ComponentType<LucideProps>;
}) {
  if (!colorList || colorList.length === 0) return null;
  return (
    <Section title={title} icon={icon}>
      <View style={styles.chipRow}>
        {colorList.map((c, i) => (
          <View
            key={`col-${i}`}
            style={[
              styles.colorChip,
              { borderColor: good ? colors.success : colors.danger },
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
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: spacing.xxl + spacing.sm },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm, textAlign: "center" },

  hero: { alignItems: "center", padding: spacing.xl, backgroundColor: colors.surface },
  heroImage: { width: 140, height: 140, borderRadius: br.lg, backgroundColor: "#e0e0e0" },
  heroPlaceholder: { alignItems: "center", justifyContent: "center" },
  heroInitial: { fontSize: fontSize.display, fontWeight: fontWeight.extrabold, color: colors.text.light },
  heroName: { fontSize: fontSize.xl, fontWeight: fontWeight.extrabold, marginTop: spacing.md },
  heroSub: { fontSize: fontSize.xs, color: colors.text.tertiary, marginTop: spacing.xs, textTransform: "capitalize" },

  section: {
    marginTop: spacing.sm,
    backgroundColor: colors.surface,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
  },
  sectionTitle: { fontSize: fontSize.base, fontWeight: fontWeight.bold, marginBottom: spacing.sm },

  matchCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fafafa",
    borderRadius: br.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: MIN_TOUCH_TARGET,
    ...shadow.sm,
  },
  matchInfo: { flex: 1, marginRight: spacing.sm },
  matchNameRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  matchName: { fontSize: fontSize.sm, fontWeight: fontWeight.bold, color: colors.text.primary },
  matchReason: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs },
  ownedBadge: {
    backgroundColor: colors.success + "22",
    borderRadius: br.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: spacing.xs - 2,
  },
  ownedBadgeText: { fontSize: fontSize.xs - 3, fontWeight: fontWeight.extrabold, color: colors.success },
  scoreBadge: { borderRadius: br.sm, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs + 2 },
  scoreText: { fontSize: fontSize.sm, fontWeight: fontWeight.extrabold },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  colorChip: {
    borderRadius: br.lg,
    borderWidth: 1.5,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    backgroundColor: colors.surface,
  },
  colorChipText: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold, color: colors.accent },

  occasionChip: {
    backgroundColor: colors.accent,
    borderRadius: br.lg,
    paddingHorizontal: spacing.sm + 6,
    paddingVertical: spacing.sm,
    minHeight: MIN_TOUCH_TARGET,
    justifyContent: "center",
  },
  occasionChipText: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.semibold, color: colors.text.white },

  empty: { fontSize: fontSize.xs + 1, color: colors.text.muted, fontStyle: "italic" },

  shopBlock: {
    backgroundColor: "#fafafa",
    borderRadius: br.md,
    padding: spacing.md,
    marginBottom: spacing.sm + 2,
    borderWidth: 1,
    borderColor: colors.border,
  },
  shopHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  shopName: { fontSize: fontSize.sm, fontWeight: fontWeight.bold, color: colors.text.primary },
  shopPct: { fontSize: fontSize.xs, fontWeight: fontWeight.bold, color: colors.success },
  shopReason: { fontSize: fontSize.xs, color: colors.text.secondary, marginTop: spacing.xs, marginBottom: spacing.sm + 2 },
  storeRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  storeBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.sm + 2,
    paddingHorizontal: spacing.md,
    minHeight: MIN_TOUCH_TARGET,
    justifyContent: "center",
    alignItems: "center",
  },
  storeBtnText: { fontSize: fontSize.xs, fontWeight: fontWeight.semibold, color: colors.text.white },
});
