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
import { useLocalSearchParams, useNavigation } from "expo-router";
import * as Linking from "expo-linking";
import { styleAdviceApi, StyleAdviceResponse, SuggestionWithProducts } from "../lib/api";
import { BASE_URL } from "../config/api";

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
      <View style={styles.center}>
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
              <Text style={styles.suggestionCardFallbackIcon}>🛍️</Text>
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
          <Text style={styles.suggestionCardLinkText}>🛍️ Meesho</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.suggestionCardLinkBtn}
          onPress={() => openLink(googleUrl)}
        >
          <Text style={styles.suggestionCardLinkText}>🔍 Google</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.suggestionCardTag}>
        <Text style={styles.suggestionCardTagText}>{item.suggestion}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { paddingBottom: 40 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 30 },
  loadingText: { fontSize: 14, color: "#888", marginTop: 10, textAlign: "center" },
  errorText: { fontSize: 14, color: "#c00", textAlign: "center", marginBottom: 16 },
  retryBtn: {
    backgroundColor: "#333",
    borderRadius: 10,
    paddingHorizontal: 24,
    paddingVertical: 10,
  },
  retryBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },

  adviceSection: {
    marginTop: 10,
    backgroundColor: "#fff",
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  adviceTitle: { fontSize: 17, fontWeight: "800", marginBottom: 4 },
  adviceReason: {
    fontSize: 13,
    color: "#666",
    fontStyle: "italic",
    marginBottom: 12,
    lineHeight: 18,
  },

  suggestionRow: { marginBottom: 8 },
  suggestionLabel: {
    fontSize: 12,
    fontWeight: "700",
    color: "#999",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  suggestionScroll: { gap: 10, paddingRight: 16 },
  suggestionCard: {
    width: 200,
    backgroundColor: "#fafafa",
    borderRadius: 12,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#eee",
  },
  suggestionCardImgWrap: { position: "relative" },
  suggestionCardImg: { width: "100%", height: 200, backgroundColor: "#e0e0e0" },
  suggestionCardImgPlaceholder: {},
  suggestionCardImgFallback: {
    alignItems: "center",
    justifyContent: "center",
  },
  suggestionCardFallbackIcon: { fontSize: 32, opacity: 0.3 },
  suggestionSourceBadge: {
    position: "absolute",
    top: 8,
    left: 8,
    backgroundColor: "rgba(0,0,0,0.65)",
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  suggestionSourceText: { fontSize: 11, fontWeight: "700", color: "#fff", textTransform: "capitalize" },
  suggestionCardProduct: { fontSize: 13, fontWeight: "700", color: "#222", margin: 8, marginBottom: 2 },
  suggestionCardPrice: { fontSize: 15, fontWeight: "800", color: "#333", marginHorizontal: 8, marginBottom: 4 },
  suggestionCardMore: { fontSize: 11, fontWeight: "600", color: "#6C5CE7", marginHorizontal: 8, marginBottom: 8 },
  suggestionCardTag: {
    backgroundColor: "#f0eeff",
    borderTopWidth: 1,
    borderTopColor: "#e8e5ff",
    paddingHorizontal: 8,
    paddingVertical: 5,
  },
  suggestionCardTagText: { fontSize: 11, fontWeight: "600", color: "#6C5CE7" },
  suggestionCardLinks: {
    flexDirection: "row",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 6,
  },
  suggestionCardLinkBtn: {
    flex: 1,
    backgroundColor: "#f5f5f5",
    borderRadius: 6,
    paddingVertical: 5,
    alignItems: "center",
  },
  suggestionCardLinkText: { fontSize: 11, fontWeight: "700", color: "#444" },
  suggestionCardFallback: { fontSize: 12, color: "#aaa", fontStyle: "italic", margin: 8, marginTop: 0 },
});
