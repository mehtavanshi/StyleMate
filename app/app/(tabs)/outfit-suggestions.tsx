import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  AppState,
  FlatList,
  Image,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useFocusEffect } from "expo-router";
import * as Linking from "expo-linking";
import {
  consentApi,
  ConsentStatus,
  DEMO_USER_ID,
  outfitApi,
  feedbackApi,
  shoppingApi,
  tryOnApi,
  TryOnJob,
  OutfitSuggestion,
  OutfitItem,
  ShoppingGroup,
  ShoppingProduct,
} from "../../lib/api";
import { resolvePhotoUrl } from "../../lib/constants";
import { BASE_URL } from "../../config/api";
import TryOnUsageBadge from "../../components/TryOnUsageBadge";
import {
  RefreshCw,
  Sparkles,
  Star,
  ThumbsDown,
  ThumbsUp,
} from "../../lib/icons";
import { spacing, fontSize, fontWeight, borderRadius as br, colors, shadow } from "../../theme/tokens";

const OCCASIONS = ["casual", "office", "ethnic", "party", "formal", "loungewear"];
const TARGET_GENDERS = ["unisex", "men", "women"];

const CATEGORY_COLORS: Record<string, string> = {
  top: "#4A90D9",
  bottom: "#7B68EE",
  dress: "#E91E8A",
  outerwear: "#2ECC71",
  footwear: "#E8A317",
  accessory: "#E74C3C",
};

const BREAKDOWN_COLORS: Record<string, string> = {
  color: "#4A90D9",
  embedding: "#9B59B6",
  hard_rules: "#2ECC71",
  fabric: "#E8A317",
  fit: "#E74C3C",
  season: "#1ABC9C",
};

const TRYON_MESSAGES = [
  "Fitting the garment...",
  "Matching your lighting...",
  "Almost there...",
  "Tailoring the fit...",
  "Blending colors...",
];

interface TryOnCardState {
  status: "idle" | "loading" | "processing" | "completed" | "failed";
  jobId?: string;
  error?: { type: "rate_limit" | "bad_photo" | "network"; message: string };
  result?: TryOnJob;
  messageIndex: number;
}

function scoreColor(score: number): string {
  if (score >= 0.8) return "#2ECC71";
  if (score >= 0.5) return "#E8A317";
  return "#E74C3C";
}

function ItemThumb({ item }: { item: OutfitItem }) {
  const bg = CATEGORY_COLORS[item.category] || "#999";
  const [imgFailed, setImgFailed] = useState(false);
  return (
    <TouchableOpacity
      style={styles.thumbWrap}
      activeOpacity={0.8}
      onPress={() => router.push(`/wardrobe/${item.id}`)}
      accessibilityLabel={`${item.name || item.category} - ${item.category}`}
    >
      {item.image_url && !imgFailed ? (
        <Image
          source={{ uri: resolvePhotoUrl(item.image_url, BASE_URL) }}
          style={styles.thumbImage}
          onError={() => setImgFailed(true)}
        />
      ) : (
        <View style={[styles.thumbImage, styles.thumbPlaceholder, { backgroundColor: bg + "33" }]}>
          <Text style={[styles.thumbInitial, { color: bg }]}>
            {(item.name || item.category)?.[0]?.toUpperCase() || "?"}
          </Text>
        </View>
      )}
      <View style={[styles.thumbBadge, { backgroundColor: bg }]}>
        <Text style={styles.thumbBadgeText}>{item.category}</Text>
      </View>
      {item.fabric_type && (
        <View style={[styles.attrBadge, { top: 26, backgroundColor: bg + "bb" }]}>
          <Text style={styles.attrBadgeText}>{item.fabric_type}</Text>
        </View>
      )}
      {item.fit_type && (
        <View style={[styles.attrBadge, { top: 44, backgroundColor: bg + "88" }]}>
          <Text style={styles.attrBadgeText}>{item.fit_type}</Text>
        </View>
      )}
      <View style={styles.thumbOverlay}>
        <Text style={styles.thumbName} numberOfLines={1}>{item.name || "Unnamed"}</Text>
      </View>
    </TouchableOpacity>
  );
}

function BreakdownBar({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  if (total === 0 || entries.length === 0) return null;
  return (
    <View style={styles.breakdownRow}>
      {entries.map(([key, value]) => {
        const color = BREAKDOWN_COLORS[key] || "#999";
        const pct = Math.max((value / total) * 100, 4);
        return (
          <View
            key={key}
            style={[styles.breakdownSegment, { flex: pct, backgroundColor: color }]}
          />
        );
      })}
    </View>
  );
}

function BreakdownLegend({ breakdown }: { breakdown: Record<string, number> }) {
  const entries = Object.entries(breakdown);
  return (
    <View style={styles.legendRow}>
      {entries.map(([key, value]) => (
        <View key={key} style={styles.legendItem}>
          <View style={[styles.legendDot, { backgroundColor: BREAKDOWN_COLORS[key] || "#999" }]} />
          <Text style={styles.legendLabel}>{key}</Text>
          <Text style={styles.legendValue}>{value.toFixed(2)}</Text>
        </View>
      ))}
    </View>
  );
}

function ProductCard({ item }: { item: ShoppingProduct }) {
  const [prodImgFailed, setProdImgFailed] = useState(false);

  const openAffiliate = async (link: string) => {
    if (!link) return;
    try {
      const supported = await Linking.canOpenURL(link);
      if (supported) {
        await Linking.openURL(link);
      } else {
        Alert.alert("Can't open link", link);
      }
    } catch (e: any) {
      Alert.alert("Error", e.message);
    }
  };

  // Meesho is a deep-link fallback (no real product API), so render it
  // distinctly as a "search" button — never as a specific product card
  // with price/image, which would mislead the user.
  if (item.source === "meesho") {
    return (
      <TouchableOpacity
        style={styles.meeshoButton}
        activeOpacity={0.85}
        onPress={() => openAffiliate(item.affiliate_link)}
      >
        <Text style={styles.meeshoButtonText}>🔍 Search this on Meesho</Text>
        <Text style={styles.meeshoButtonSub} numberOfLines={1}>
          {item.name}
        </Text>
      </TouchableOpacity>
    );
  }

  return (
    <TouchableOpacity
      style={styles.productCard}
      activeOpacity={0.85}
      onPress={() => openAffiliate(item.affiliate_link)}
    >
      {item.image_url && !prodImgFailed ? (
        <Image
          source={{ uri: item.image_url }}
          style={styles.productImage}
          onError={() => setProdImgFailed(true)}
        />
      ) : (
        <View style={[styles.productImage, styles.productImagePlaceholder]}>
          <Text style={styles.productInitial}>
            {(item.name || "?")[0]?.toUpperCase()}
          </Text>
        </View>
      )}
      <Text style={styles.productName} numberOfLines={2}>
        {item.name}
      </Text>
      <Text style={styles.productPrice}>
        {item.currency} {item.price.toFixed(2)}
      </Text>
    </TouchableOpacity>
  );
}

export default function OutfitSuggestionsScreen() {
  const [suggestions, setSuggestions] = useState<OutfitSuggestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOccasion, setSelectedOccasion] = useState<string | null>(null);
  const [selectedTargetGender, setSelectedTargetGender] = useState<string | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<Record<string, boolean>>({});
  const [pendingFeedback, setPendingFeedback] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);
  const [shoppingGroups, setShoppingGroups] = useState<ShoppingGroup[]>([]);
  const [shoppingLoading, setShoppingLoading] = useState(true);
  const [shoppingError, setShoppingError] = useState(false);
  const [hasPhoto, setHasPhoto] = useState(false);
  const [tryOnStates, setTryOnStates] = useState<Record<string, TryOnCardState>>({});
  const pollRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  const messageRefs = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  const appStateRef = useRef(AppState.currentState);
  const tryOnStatesRef = useRef(tryOnStates);
  tryOnStatesRef.current = tryOnStates;
  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 1800);
  };

  const loadShopping = useCallback(async () => {
    setShoppingLoading(true);
    try {
      const data = await shoppingApi.suggest({
        target_gender: selectedTargetGender || undefined,
        occasion_tag: selectedOccasion || undefined,
      });
      setShoppingGroups(data);
      setShoppingError(false);
    } catch (e: any) {
      console.warn("Shopping suggestions failed:", e.message);
      setShoppingGroups([]);
      setShoppingError(true);
    } finally {
      setShoppingLoading(false);
    }
  }, [selectedOccasion, selectedTargetGender]);

  const loadSuggestions = useCallback(async () => {
    setLoading(true);
    try {
      const data = await outfitApi.suggest({
        occasion_tag: selectedOccasion || undefined,
        target_gender: selectedTargetGender || undefined,
      });
      setSuggestions(data);
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setLoading(false);
    }
  }, [selectedOccasion, selectedTargetGender]);

  useFocusEffect(
    useCallback(() => {
      loadSuggestions();
      loadShopping();
      consentApi
        .getStatus(DEMO_USER_ID)
        .then((s: ConsentStatus) => setHasPhoto(!!s.photo_consent && !!s.photo_url))
        .catch(() => {});
    }, [selectedOccasion, selectedTargetGender, loadSuggestions, loadShopping])
  );

  useEffect(() => {
    const activePolls = pollRefs.current;
    const activeMessages = messageRefs.current;
    return () => {
      Object.values(activePolls).forEach(clearInterval);
      Object.values(activeMessages).forEach(clearInterval);
    };
  }, []);

  // Re-poll in-flight try-ons when app returns to foreground
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (nextState) => {
      const wasBg = appStateRef.current.match(/inactive|background/);
      appStateRef.current = nextState;

      if (wasBg && nextState === "active") {
        const states = tryOnStatesRef.current;
        Object.entries(states).forEach(([key, state]) => {
          if (state.status === "processing" && state.jobId) {
            tryOnApi
              .poll(state.jobId)
              .then((updated) => {
                if (updated.status === "completed" || updated.status === "failed") {
                  clearInterval(pollRefs.current[key]);
                  clearInterval(messageRefs.current[key]);
                  delete pollRefs.current[key];
                  delete messageRefs.current[key];

                  if (updated.status === "completed") {
                    setTryOnStates((prev) => ({ ...prev, [key]: { ...prev[key], status: "completed", result: updated } }));
                    router.push(`/try-on?job_id=${updated.job_id}`);
                  } else {
                    let errorType: "rate_limit" | "bad_photo" | "network" = "network";
                    if (updated.error_type === "bad_photo") errorType = "bad_photo";
                    else if (updated.error_type === "rate_limit") errorType = "rate_limit";
                    setTryOnStates((prev) => ({
                      ...prev,
                      [key]: {
                        ...prev[key],
                        status: "failed",
                        error: { type: errorType, message: updated.error_message || "Try-on failed" },
                      },
                    }));
                  }
                }
              })
              .catch(() => {});
          }
        });
      }
    });

    return () => subscription.remove();
  }, []);

  const rotateMessages = useCallback((key: string) => {
    messageRefs.current[key] = setInterval(() => {
      setTryOnStates((prev) => {
        const s = prev[key];
        if (!s || s.status === "idle" || s.status === "completed" || s.status === "failed") {
          return prev;
        }
        return { ...prev, [key]: { ...s, messageIndex: (s.messageIndex + 1) % TRYON_MESSAGES.length } };
      });
    }, 3000);
  }, []);

  const startTryOn = useCallback(async (key: string, garmentIds: number[]) => {
    setTryOnStates((prev) => ({ ...prev, [key]: { status: "loading", messageIndex: 0 } }));
    rotateMessages(key);

    try {
      const job = await tryOnApi.render(garmentIds);
      setTryOnStates((prev) => ({ ...prev, [key]: { ...prev[key], status: "processing", jobId: job.job_id } }));

      pollRefs.current[key] = setInterval(async () => {
        try {
          const updated = await tryOnApi.poll(job.job_id);
          if (updated.status === "completed" || updated.status === "failed") {
            clearInterval(pollRefs.current[key]);
            clearInterval(messageRefs.current[key]);
            delete pollRefs.current[key];
            delete messageRefs.current[key];

            if (updated.status === "completed") {
              setTryOnStates((prev) => ({ ...prev, [key]: { ...prev[key], status: "completed", result: updated } }));
              router.push(`/try-on?job_id=${updated.job_id}`);
            } else {
              let errorType: "rate_limit" | "bad_photo" | "network" = "network";
              if (updated.error_type === "bad_photo") errorType = "bad_photo";
              else if (updated.error_type === "rate_limit") errorType = "rate_limit";
              setTryOnStates((prev) => ({
                ...prev,
                [key]: {
                  ...prev[key],
                  status: "failed",
                  error: { type: errorType, message: updated.error_message || "Try-on failed" },
                },
              }));
            }
          }
        } catch {
          clearInterval(pollRefs.current[key]);
          clearInterval(messageRefs.current[key]);
          delete pollRefs.current[key];
          delete messageRefs.current[key];
          setTryOnStates((prev) => ({
            ...prev,
            [key]: {
              ...prev[key],
              status: "failed",
              error: { type: "network", message: "Could not check try-on status. Please try again." },
            },
          }));
        }
      }, 2000);
    } catch (e: any) {
      clearInterval(messageRefs.current[key]);
      delete messageRefs.current[key];

      if (e.rateLimit) {
        setTryOnStates((prev) => ({
          ...prev,
          [key]: {
            ...prev[key],
            status: "failed",
            error: { type: "rate_limit", message: e.rateLimit.message || "Daily try-on limit exceeded." },
          },
        }));
      } else {
        setTryOnStates((prev) => ({
          ...prev,
          [key]: {
            ...prev[key],
            status: "failed",
            error: { type: "network", message: "Something went wrong. Please try again." },
          },
        }));
      }
    }
  }, [rotateMessages]);

  const submitFeedback = async (key: string, itemIds: number[], liked: boolean) => {
    if (feedbackGiven[key] || pendingFeedback[key]) return;
    setPendingFeedback((p) => ({ ...p, [key]: true }));
    try {
      await feedbackApi.create(itemIds, liked);
      setFeedbackGiven((g) => ({ ...g, [key]: true }));
      showToast(liked ? "Liked outfit" : "Noted — outfit disliked");
    } catch (e: any) {
      Alert.alert("Error", e.message);
    } finally {
      setPendingFeedback((p) => ({ ...p, [key]: false }));
    }
  };

  const renderCard = ({ item, index }: { item: OutfitSuggestion; index: number }) => {
    const key = `suggestion-${index}`;
    const given = feedbackGiven[key];
    const pending = pendingFeedback[key];
    const itemIds = item.items.map((o) => o.id);
    const tryOnState = tryOnStates[key] || { status: "idle", messageIndex: 0 };
    const isTryOnActive = tryOnState.status === "loading" || tryOnState.status === "processing";

    return (
      <View style={[styles.card, given && styles.cardFeedbackGiven]}>
        <View style={styles.cardImages}>
          {item.items.map((outfitItem) => (
            <View key={outfitItem.id} style={styles.thumbOuter}>
              <ItemThumb item={outfitItem} />
            </View>
          ))}
          {isTryOnActive && (
            <View style={styles.tryonOverlay} accessibilityRole="progressbar" accessibilityLabel="Generating virtual try-on">
              <ActivityIndicator size="large" color="#fff" />
              <Text style={styles.tryonOverlayText}>
                {TRYON_MESSAGES[tryOnState.messageIndex]}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.cardFooter}>
          <Text style={styles.reasonText}>{item.reason}</Text>
          <View style={[styles.scoreBadge, { backgroundColor: scoreColor(item.score) + "22" }]}>
            <View style={{ flexDirection: "row", alignItems: "center", gap: 3 }}>
              <Star size={14} color={scoreColor(item.score)} strokeWidth={1.5} fill={scoreColor(item.score)} />
              <Text style={[styles.scoreText, { color: scoreColor(item.score) }]}>
                {item.score.toFixed(2)}
              </Text>
            </View>
          </View>
        </View>
        <BreakdownBar breakdown={item.breakdown || {}} />
        <BreakdownLegend breakdown={item.breakdown || {}} />

        <View style={styles.feedbackRow}>
          <TouchableOpacity
            style={[styles.feedbackBtn, given && styles.feedbackBtnDisabled]}
            disabled={given || pending}
            onPress={() => submitFeedback(key, itemIds, true)}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
              <ThumbsUp size={16} color={given ? "#999" : "#333"} strokeWidth={1.5} />
              <Text style={[styles.feedbackBtnText, given && styles.feedbackBtnTextDone]}>
                {given ? "Saved" : "Like"}
              </Text>
            </View>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.feedbackBtn, styles.feedbackBtnDislike, given && styles.feedbackBtnDisabled]}
            disabled={given || pending}
            onPress={() => submitFeedback(key, itemIds, false)}
          >
            <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
              <ThumbsDown size={16} color={given ? "#999" : "#333"} strokeWidth={1.5} />
              <Text style={[styles.feedbackBtnText, given && styles.feedbackBtnTextDone]}>
                {given ? "Saved" : "Dislike"}
              </Text>
            </View>
          </TouchableOpacity>
        </View>

        <View style={styles.tryonRow}>
          {!hasPhoto ? (
            <View>
              <TouchableOpacity
                style={[styles.tryonBtn, styles.tryonBtnDisabled]}
                onPress={() => router.push("/capture")}
              >
                <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                  <Sparkles size={16} color="#fff" strokeWidth={1.5} />
                  <Text style={styles.tryonBtnText}>Try It On</Text>
                </View>
              </TouchableOpacity>
              <Text style={styles.tryonSubtext}>Upload a photo first to try on outfits</Text>
            </View>
          ) : (
            <>
              <TouchableOpacity
                style={[styles.tryonBtn, isTryOnActive && styles.tryonBtnLoading]}
                disabled={isTryOnActive}
                onPress={() => {
                  if (itemIds.length > 0) startTryOn(key, itemIds);
                }}
              >
                {tryOnState.status === "loading" || tryOnState.status === "processing" ? (
                  <Text style={styles.tryonBtnText}>
                    {tryOnState.status === "loading" ? "Starting..." : "Processing..."}
                  </Text>
                ) : (
                  <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
                    <Sparkles size={16} color="#fff" strokeWidth={1.5} />
                    <Text style={styles.tryonBtnText}>Try It On</Text>
                  </View>
                )}
              </TouchableOpacity>
              {tryOnState.status === "failed" && tryOnState.error && (
                <View style={styles.tryonErrorBox} accessibilityLabel={`Try-on error: ${tryOnState.error.message}`}>
                  <Text style={styles.tryonErrorText}>{tryOnState.error.message}</Text>
                  {tryOnState.error.type === "bad_photo" && (
                    <TouchableOpacity onPress={() => router.push("/capture")}>
                      <Text style={styles.tryonErrorAction}>Retake photo</Text>
                    </TouchableOpacity>
                  )}
                  {tryOnState.error.type === "network" && (
                    <TouchableOpacity
                      onPress={() => {
                        if (itemIds.length > 0) startTryOn(key, itemIds);
                      }}
                    >
                      <Text style={styles.tryonErrorAction}>Retry</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
            </>
          )}
        </View>
      </View>
    );
  };

  const renderProductCard = ({ item }: { item: ShoppingProduct }) => (
    <ProductCard item={item} />
  );

  const CompleteTheLook = () => {
    if (shoppingLoading) {
      return (
        <View style={styles.shoppingSection}>
          <Text style={styles.shoppingHeading}>Complete the Look</Text>
          <View style={styles.shoppingRow}>
            {[0, 1, 2].map((i) => (
              <View key={i} style={styles.productCard}>
                <View style={[styles.productImage, styles.skeleton]} />
                <View style={[styles.skeletonLine, { width: "80%" }]} />
                <View style={[styles.skeletonLine, { width: "50%" }]} />
              </View>
            ))}
          </View>
        </View>
      );
    }

    if (!shoppingGroups || shoppingGroups.length === 0) {
      if (shoppingError) {
        return (
          <View style={styles.shoppingSection}>
            <Text style={styles.shoppingHeading}>Complete the Look</Text>
            <Text style={styles.shoppingErrorText}>
              Could not load suggestions. Check your connection.
            </Text>
          </View>
        );
      }
      return (
        <View style={styles.shoppingSection}>
          <Text style={styles.shoppingHeading}>Complete the Look</Text>
          <Text style={styles.shoppingEmpty}>
            No suggestions right now — your wardrobe looks well rounded!
          </Text>
        </View>
      );
    }

    return (
      <View style={styles.shoppingSection}>
        <Text style={styles.shoppingHeading}>Complete the Look</Text>
        {shoppingGroups.map((group, gi) => (
          <View key={`${group.missing_category}-${gi}`} style={styles.gapBlock}>
            <Text style={styles.gapReason}>{group.gap_reason}</Text>
            {group.products.length === 0 ? (
              <Text style={styles.gapNoProducts}>
                No matches found right now.
              </Text>
            ) : (
              <FlatList
                horizontal
                showsHorizontalScrollIndicator={false}
                data={group.products}
                keyExtractor={(p, i) => `${group.missing_category}-${i}`}
                contentContainerStyle={styles.shoppingRow}
                renderItem={renderProductCard}
              />
            )}
          </View>
        ))}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} accessibilityRole="none">
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">Outfit Suggestions</Text>
        <TouchableOpacity style={styles.refreshBtn} onPress={loadSuggestions} accessibilityLabel="Refresh outfit suggestions">
          <View style={{ flexDirection: "row", alignItems: "center", gap: 4 }}>
            <RefreshCw size={18} color="#333" strokeWidth={1.5} />
            <Text style={styles.refreshBtnText}>Refresh</Text>
          </View>
        </TouchableOpacity>
      </View>

      <TryOnUsageBadge />

      {/* Occasion chips */}
      <View style={styles.chipBar}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={OCCASIONS}
          keyExtractor={(o) => o}
          contentContainerStyle={styles.chipList}
          renderItem={({ item: o }) => {
            const active = selectedOccasion === o;
            return (
              <TouchableOpacity
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setSelectedOccasion(active ? null : o)}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{o}</Text>
              </TouchableOpacity>
            );
          }}
        />
      </View>

      {/* Gender chips */}
      <View style={styles.chipBar}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={TARGET_GENDERS}
          keyExtractor={(g) => g}
          contentContainerStyle={styles.chipList}
          renderItem={({ item: g }) => {
            const active = selectedTargetGender === g;
            return (
              <TouchableOpacity
                style={[styles.chip, active && styles.chipActive]}
                onPress={() => setSelectedTargetGender(active ? null : g)}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{g}</Text>
              </TouchableOpacity>
            );
          }}
        />
      </View>

      {/* Content */}
      {loading ? (
        <View style={styles.center} accessibilityRole="progressbar" accessibilityLabel="Generating outfit suggestions">
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Generating outfits...</Text>
        </View>
      ) : suggestions.length === 0 ? (
        <View style={styles.center}>
          <Text style={styles.emptyTitle}>No outfit suggestions</Text>
          <Text style={styles.emptyText}>
            {selectedOccasion
              ? `No outfits match the "${selectedOccasion}" occasion. Try clearing the filter.`
              : "Add items to your wardrobe to get outfit suggestions."}
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.list}>
          {suggestions.map((item, index) => (
            <View key={`suggestion-${index}`}>{renderCard({ item, index })}</View>
          ))}
          <CompleteTheLook />
        </ScrollView>
      )}

      <Modal visible={toast !== null} transparent animationType="fade">
        <View style={styles.toastWrap}>
          <View style={styles.toastBox}>
            <Text style={styles.toastText}>{toast}</Text>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xxl },
  loadingText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm + 2 },

  // Header
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    backgroundColor: colors.surface,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { fontSize: fontSize.xl, fontWeight: fontWeight.bold },
  refreshBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.sm + 2,
    paddingHorizontal: spacing.sm + 6,
    paddingVertical: spacing.sm,
  },
  refreshBtnText: { color: colors.text.white, fontSize: fontSize.sm, fontWeight: fontWeight.semibold },

  // Chips
  chipBar: { backgroundColor: colors.surface, paddingBottom: spacing.sm + 2, borderBottomWidth: 1, borderBottomColor: colors.border },
  chipList: { paddingHorizontal: spacing.md, paddingTop: spacing.sm + 2 },
  chip: { paddingHorizontal: spacing.sm + 6, paddingVertical: spacing.xs + 3, borderRadius: 20, backgroundColor: "#e8e8e8", marginRight: spacing.sm },
  chipActive: { backgroundColor: colors.accent },
  chipText: { fontSize: fontSize.xs + 1, color: "#666", textTransform: "capitalize" },
  chipTextActive: { color: colors.text.white },

  // List
  list: { padding: spacing.md },

  // Card
  card: {
    backgroundColor: colors.surface,
    borderRadius: br.lg - 2,
    overflow: "hidden",
    marginBottom: spacing.sm + 6,
    ...shadow.md,
  },
  cardFeedbackGiven: { opacity: 0.6 },
  feedbackRow: {
    flexDirection: "row",
    gap: spacing.sm + 2,
    paddingHorizontal: spacing.sm + 6,
    paddingBottom: spacing.sm + 6,
    paddingTop: spacing.xs + 2,
  },
  feedbackBtn: {
    flex: 1,
    backgroundColor: colors.success + "55",
    borderRadius: br.md,
    paddingVertical: spacing.sm + 2,
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.success,
  },
  feedbackBtnDislike: {
    backgroundColor: colors.danger + "33",
    borderColor: colors.danger,
  },
  feedbackBtnDisabled: {
    backgroundColor: "#eeeeee",
    borderColor: "#cccccc",
  },
  feedbackBtnText: { fontSize: fontSize.sm, fontWeight: fontWeight.bold, color: "#1c1c1c" },
  feedbackBtnTextDone: { color: colors.text.light },

  // Toast
  toastWrap: {
    flex: 1,
    justifyContent: "flex-end",
    alignItems: "center",
    paddingBottom: spacing.xxl + spacing.sm,
    backgroundColor: "transparent",
  },
  toastBox: {
    backgroundColor: "rgba(0,0,0,0.82)",
    borderRadius: br.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    maxWidth: "85%",
  },
  toastText: { color: colors.text.white, fontSize: fontSize.sm, fontWeight: fontWeight.semibold, textAlign: "center" },
  cardImages: {
    flexDirection: "row",
    padding: spacing.sm + 2,
    gap: spacing.sm + 2,
  },
  thumbOuter: { flex: 1 },
  thumbWrap: { position: "relative", borderRadius: br.md, overflow: "hidden" },
  thumbImage: { width: "100%", aspectRatio: 1, borderRadius: br.md, backgroundColor: "#e0e0e0" },
  thumbPlaceholder: { alignItems: "center", justifyContent: "center" },
  thumbInitial: { fontSize: fontSize.xxl, fontWeight: fontWeight.bold },
  thumbBadge: {
    position: "absolute",
    top: spacing.xs + 2,
    left: spacing.xs + 2,
    borderRadius: br.sm - 1,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: spacing.xs - 2,
  },
  thumbBadgeText: { color: colors.text.white, fontSize: 9, fontWeight: fontWeight.bold, textTransform: "uppercase" },
  attrBadge: {
    position: "absolute",
    left: spacing.xs + 2,
    borderRadius: spacing.xs,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  attrBadgeText: { color: colors.text.white, fontSize: 8, fontWeight: fontWeight.semibold, textTransform: "uppercase" },
  thumbOverlay: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: "rgba(0,0,0,0.4)",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderBottomLeftRadius: br.md,
    borderBottomRightRadius: br.md,
  },
  thumbName: { color: colors.text.white, fontSize: 11, fontWeight: fontWeight.semibold },

  // Card footer
  cardFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: spacing.sm + 6,
    paddingVertical: spacing.md,
    borderTopWidth: 1,
    borderTopColor: "#f0f0f0",
  },
  reasonText: { flex: 1, fontSize: fontSize.xs + 1, color: "#666", fontStyle: "italic", marginRight: spacing.sm + 2 },
  scoreBadge: { borderRadius: br.sm + 2, paddingHorizontal: spacing.sm + 2, paddingVertical: spacing.xs },
  scoreText: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold },

  // Empty
  emptyTitle: { fontSize: fontSize.lg, fontWeight: fontWeight.semibold, marginBottom: spacing.sm },
  emptyText: { fontSize: fontSize.sm, color: colors.text.tertiary, textAlign: "center", lineHeight: 22 },

  // Try on
  tryonRow: {
    paddingHorizontal: spacing.sm + 6,
    paddingBottom: spacing.sm + 6,
  },
  tryonBtn: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  tryonBtnText: {
    color: colors.text.white,
    fontSize: fontSize.sm + 1,
    fontWeight: fontWeight.bold,
  },
  tryonBtnDisabled: {
    backgroundColor: "#bbb",
  },
  tryonBtnLoading: {
    backgroundColor: "#666",
  },
  tryonSubtext: {
    fontSize: fontSize.xs,
    color: colors.text.tertiary,
    marginTop: spacing.xs + 2,
    textAlign: "center",
  },
  tryonOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderRadius: br.md,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  tryonOverlayText: {
    color: colors.text.white,
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.semibold,
  },
  tryonErrorBox: {
    backgroundColor: "#FFF0F0",
    borderRadius: br.sm + 2,
    padding: spacing.sm + 2,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger + "33",
  },
  tryonErrorText: {
    fontSize: fontSize.xs,
    color: "#C0392B",
    marginBottom: spacing.xs,
    lineHeight: 18,
  },
  tryonErrorAction: {
    fontSize: fontSize.xs + 1,
    color: colors.danger,
    fontWeight: fontWeight.bold,
    textDecorationLine: "underline",
  },

  breakdownRow: {
    flexDirection: "row",
    height: spacing.xs,
    marginHorizontal: spacing.sm + 6,
    marginBottom: spacing.xs + 2,
    borderRadius: spacing.xs - 2,
    overflow: "hidden",
    backgroundColor: "#eee",
  },
  breakdownSegment: {
    height: "100%",
  },
  legendRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    paddingHorizontal: spacing.sm + 6,
    paddingBottom: spacing.sm + 2,
    gap: spacing.sm,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: spacing.xs - 1 },
  legendDot: { width: spacing.xs + 2, height: spacing.xs + 2, borderRadius: spacing.xs - 1 },
  legendLabel: { fontSize: fontSize.xs - 2, color: colors.text.tertiary, textTransform: "capitalize" },
  legendValue: { fontSize: fontSize.xs - 2, color: "#555", fontWeight: fontWeight.semibold },

  // Complete the Look
  shoppingSection: {
    backgroundColor: colors.surface,
    marginTop: spacing.xs + 2,
    paddingVertical: spacing.sm + 6,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  shoppingHeading: {
    fontSize: fontSize.base + 1,
    fontWeight: fontWeight.bold,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  shoppingRow: { paddingHorizontal: spacing.lg, gap: spacing.md },
  shoppingEmpty: {
    fontSize: fontSize.sm,
    color: colors.text.tertiary,
    paddingHorizontal: spacing.lg,
    lineHeight: 22,
  },
  shoppingErrorText: {
    fontSize: fontSize.sm,
    color: colors.danger,
    paddingHorizontal: spacing.lg,
    lineHeight: 22,
  },
  gapBlock: { marginBottom: 18 },
  gapReason: {
    fontSize: fontSize.xs + 1,
    color: "#444",
    fontStyle: "italic",
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm + 2,
  },
  gapNoProducts: {
    fontSize: fontSize.xs + 1,
    color: colors.text.muted,
    paddingHorizontal: spacing.lg,
  },
  productCard: {
    width: 140,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.sm,
  },
  meeshoButton: {
    width: 160,
    backgroundColor: colors.surface,
    borderRadius: br.md,
    borderWidth: 1.5,
    borderColor: "#E5408A",
    paddingVertical: spacing.sm + 6,
    paddingHorizontal: spacing.md,
    alignItems: "center",
    justifyContent: "center",
  },
  meeshoButtonText: {
    fontSize: fontSize.xs + 1,
    fontWeight: fontWeight.bold,
    color: "#E5408A",
    textAlign: "center",
  },
  meeshoButtonSub: {
    fontSize: 11,
    color: colors.text.light,
    marginTop: spacing.xs,
    textAlign: "center",
  },
  productImage: {
    width: "100%",
    height: 120,
    borderRadius: br.sm + 2,
    backgroundColor: "#e0e0e0",
    marginBottom: spacing.sm,
  },
  productImagePlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  productInitial: { fontSize: 28, fontWeight: fontWeight.bold, color: colors.text.light },
  productName: { fontSize: fontSize.xs, color: colors.text.primary, height: 32, marginBottom: spacing.xs },
  productPrice: { fontSize: fontSize.xs + 1, fontWeight: fontWeight.bold, color: colors.success },
  skeleton: { backgroundColor: "#e6e6e6" },
  skeletonLine: {
    height: spacing.sm + 2,
    borderRadius: spacing.xs,
    backgroundColor: "#e6e6e6",
    marginBottom: spacing.xs + 2,
  },
});
