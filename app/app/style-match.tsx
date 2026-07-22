import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Image,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useNavigation } from "expo-router";
import * as Linking from "expo-linking";
import { styleAdviceApi, StyleAdviceResponse, SuggestionWithProducts } from "../lib/api";
import { BASE_URL } from "../config/api";
import { Search, ShoppingBag } from "../lib/icons";
import { spacing, fontSize, fontWeight, borderRadius as br, colors, shadow } from "../theme/tokens";

function imageUrl(raw: string | null | undefined): string | null {
  if (!raw) return null;
  if (raw.startsWith("http")) return raw;
  return `${BASE_URL}${raw}`;
}

function formatPrice(price: number, currency: string): string {
  const sym = currency === "INR" ? "₹" : currency + " ";
  return sym + price.toFixed(0);
}

function openLink(url: string | null | undefined) {
  if (!url) return;
  Linking.openURL(url);
}

export default function StyleMatchScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const navigation = useNavigation();
  const [advice, setAdvice] = useState<StyleAdviceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: "Style Match", headerShown: true });
  }, [navigation]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await styleAdviceApi.get(Number(id));
        if (!cancelled) {
          setAdvice(res);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [id]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await styleAdviceApi.get(Number(id));
      setAdvice(res);
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Getting AI style advice">
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Getting AI style advice…</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => {
          setLoading(true);
          styleAdviceApi.get(Number(id))
            .then((res) => { setAdvice(res); setError(null); })
            .catch((e: any) => setError(e.message))
            .finally(() => setLoading(false));
        }}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const { shoes, accessories, layering, reasoning } = advice ?? {};
  const hasAny = (shoes && shoes.length > 0) || (accessories && accessories.length > 0) || (layering && layering.length > 0);

  if (!hasAny) {
    return (
      <View style={styles.center}>
        <Text style={styles.loadingText}>No style advice available for this item.</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={{ flex: 1 }}>
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#333" />
      }
    >
      <View style={styles.adviceSection}>
        <Text style={styles.adviceTitle}>Style Match</Text>
        {reasoning ? <Text style={styles.adviceReason}>{reasoning}</Text> : null}

        {shoes && shoes.length > 0 && <SuggestionRow label="Shoes" items={shoes} />}
        {accessories && accessories.length > 0 && <SuggestionRow label="Accessories" items={accessories} />}
        {layering && layering.length > 0 && <SuggestionRow label="Layering" items={layering} />}
      </View>
    </ScrollView>
    </SafeAreaView>
  );
}

function SuggestionRow({ label, items }: { label: string; items: SuggestionWithProducts[] }) {
  return (
    <View style={styles.suggestionRow}>
      <Text style={styles.suggestionLabel}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.suggestionScroll}>
        {items.map((item, i) => (
          <SuggestionCard key={`${label}-${i}`} item={item} />
        ))}
      </ScrollView>
    </View>
  );
}

function SuggestionCard({ item }: { item: SuggestionWithProducts }) {
  const topProduct = item.products[0];
  const extraCount = item.products.length - 1;
  const productImage = topProduct?.image_url ? imageUrl(topProduct.image_url) : null;

  const meeshoUrl = topProduct?.affiliate_link;
  const googleUrl =
    `https://www.google.com/search?tbm=shop&q=${encodeURIComponent(item.suggestion)}`;

  return (
    <View style={styles.suggestionCard}>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => openLink(meeshoUrl || googleUrl)}
      >
        <View style={styles.suggestionCardImgWrap}>
          {productImage ? (
            <Image source={{ uri: productImage }} style={styles.suggestionCardImg} />
          ) : (
            <View style={[styles.suggestionCardImg, styles.suggestionCardImgFallback]}>
              <ShoppingBag size={32} color="#ccc" strokeWidth={1.5} />
            </View>
          )}
          {topProduct && (
            <View style={styles.suggestionSourceBadge}>
              <Text style={styles.suggestionSourceText}>{topProduct.source}</Text>
            </View>
          )}
        </View>
        <Text style={styles.suggestionCardProduct} numberOfLines={2}>
          {topProduct?.name || item.suggestion}
        </Text>
        {topProduct && topProduct.price > 0 && (
          <Text style={styles.suggestionCardPrice}>
            {formatPrice(topProduct.price, topProduct.currency)}
          </Text>
        )}
        {extraCount > 0 && <Text style={styles.suggestionCardMore}>+{extraCount} more</Text>}
      </TouchableOpacity>

      <View style={styles.suggestionCardLinks}>
        <TouchableOpacity
          style={styles.suggestionCardLinkBtn}
          onPress={() => openLink(meeshoUrl || googleUrl)}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <ShoppingBag size={16} color="#333" strokeWidth={1.5} />
            <Text style={styles.suggestionCardLinkText}>Meesho</Text>
          </View>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.suggestionCardLinkBtn}
          onPress={() => openLink(googleUrl)}
        >
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <Search size={16} color="#333" strokeWidth={1.5} />
            <Text style={styles.suggestionCardLinkText}>Google</Text>
          </View>
        </TouchableOpacity>
      </View>

      <View style={styles.suggestionCardTag}>
        <Text style={styles.suggestionCardTagText}>{item.suggestion}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: spacing.xxl + spacing.sm },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl + 6 },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm + 2, textAlign: "center" },
  errorText: { fontSize: fontSize.sm, color: colors.danger, textAlign: "center", marginBottom: spacing.lg },
  retryBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm + 2,
  },
  retryBtnText: { color: colors.text.white, fontWeight: fontWeight.bold, fontSize: fontSize.sm },

  adviceSection: {
    marginTop: spacing.sm + 2,
    backgroundColor: colors.surface,
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.lg,
  },
  adviceTitle: { fontSize: fontSize.base + 1, fontWeight: fontWeight.extrabold, marginBottom: spacing.xs },
  adviceReason: {
    fontSize: fontSize.xs + 1,
    color: "#666",
    fontStyle: "italic",
    marginBottom: spacing.md,
    lineHeight: 18,
  },

  suggestionRow: { marginBottom: spacing.sm },
  suggestionLabel: {
    fontSize: fontSize.xs,
    fontWeight: fontWeight.bold,
    color: colors.text.light,
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: spacing.xs + 2,
  },
  suggestionScroll: { gap: spacing.sm + 2, paddingRight: spacing.lg },
  suggestionCard: {
    width: 200,
    backgroundColor: "#fafafa",
    borderRadius: br.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
  },
  suggestionCardImgWrap: { position: "relative" },
  suggestionCardImg: { width: "100%", height: 200, backgroundColor: "#e0e0e0" },
  suggestionCardImgPlaceholder: {},
  suggestionCardImgFallback: {
    alignItems: "center",
    justifyContent: "center",
  },
  suggestionCardFallbackIcon: { fontSize: fontSize.xxl + 8, opacity: 0.3 },
  suggestionSourceBadge: {
    position: "absolute",
    top: spacing.sm,
    left: spacing.sm,
    backgroundColor: "rgba(0,0,0,0.65)",
    borderRadius: br.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs - 1,
  },
  suggestionSourceText: { fontSize: 11, fontWeight: fontWeight.bold, color: colors.text.white, textTransform: "capitalize" },
  suggestionCardProduct: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold, color: "#222", margin: spacing.sm, marginBottom: spacing.xs - 2 },
  suggestionCardPrice: { fontSize: fontSize.sm + 1, fontWeight: fontWeight.extrabold, color: colors.accent, marginHorizontal: spacing.sm, marginBottom: spacing.xs },
  suggestionCardMore: { fontSize: 11, fontWeight: fontWeight.semibold, color: "#6C5CE7", marginHorizontal: spacing.sm, marginBottom: spacing.sm },
  suggestionCardTag: {
    backgroundColor: "#f0eeff",
    borderTopWidth: 1,
    borderTopColor: "#e8e5ff",
    paddingHorizontal: spacing.sm,
    paddingVertical: br.sm - 1,
  },
  suggestionCardTagText: { fontSize: 11, fontWeight: fontWeight.semibold, color: "#6C5CE7" },
  suggestionCardLinks: {
    flexDirection: "row",
    gap: spacing.xs,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs + 2,
  },
  suggestionCardLinkBtn: {
    flex: 1,
    backgroundColor: "#f5f5f5",
    borderRadius: br.sm,
    paddingVertical: br.sm - 1,
    alignItems: "center",
  },
  suggestionCardLinkText: { fontSize: 11, fontWeight: fontWeight.bold, color: "#444" },
  suggestionCardFallback: { fontSize: fontSize.xs, color: colors.text.muted, fontStyle: "italic", margin: spacing.sm, marginTop: 0 },
});
