import { BASE_URL } from "../config/api";
import { CURRENT_CONSENT_VERSION } from "./constants";
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "./tokenStore";

export interface ClothingItem {
  id: number;
  user_id: number;
  name: string | null;
  category: string;
  subcategory: string | null;
  color: string | null;
  brand: string | null;
  pattern: string | null;
  season: string | null;
  occasion_tag: string | null;
  formality: string | null;
  target_gender: string | null;
  fabric_type: string | null;
  fit_type: string | null;
  sleeve_length: string | null;
  garment_length: string | null;
  formality_score: number | null;
  embellishments: string | null;
  style_tags: string | null;
  image_url: string | null;
  tags: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface User {
  id: number;
  name: string;
  email: string;
  gender: string | null;
  target_gender: string | null;
  style_preference: string | null;
  body_type: string | null;
  photo_consent: boolean;
  consent_given_at: string | null;
  consent_version: string | null;
  photo_url: string | null;
  created_at: string;
}

export interface ConsentStatus {
  photo_consent: boolean;
  consent_given_at: string | null;
  consent_version: string | null;
  photo_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

// ── Authenticated fetch with single-flight silent refresh ──

let refreshInFlight: Promise<string | null> | null = null;
let authExpiredNotified = false;
let onAuthExpired: (() => void) | null = null;

/** Register the handler invoked when tokens can no longer be refreshed. */
export function setOnAuthExpired(handler: () => void): void {
  onAuthExpired = handler;
}

function notifyAuthExpired(): void {
  if (authExpiredNotified) return;
  authExpiredNotified = true;
  onAuthExpired?.();
}

function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.exp === "number" && payload.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

async function performRefresh(): Promise<string | null> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { access_token: string; refresh_token: string };
    await setTokens(data.access_token, data.refresh_token);
    authExpiredNotified = false;
    return data.access_token;
  } catch {
    return null;
  }
}

function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

async function getValidAccessToken(): Promise<string | null> {
  const token = await getAccessToken();
  if (token && !isTokenExpired(token)) return token;
  return refreshAccessToken();
}

/** Low-level request: attaches auth, silently refreshes once on 401. */
async function request(path: string, options: RequestInit = {}): Promise<Response> {
  const isAuthRoute = path.startsWith("/auth/");
  const headers = new Headers(options.headers);
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!isFormData) headers.set("Content-Type", "application/json");

  if (!isAuthRoute) {
    const token = await getValidAccessToken();
    if (!token) {
      await clearTokens();
      notifyAuthExpired();
      throw new Error("Not authenticated");
    }
    headers.set("Authorization", `Bearer ${token}`);
  }

  let res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!isAuthRoute && res.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      headers.set("Authorization", `Bearer ${newToken}`);
      res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
    }
    if (res.status === 401) {
      await clearTokens();
      notifyAuthExpired();
    }
  }
  return res;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await request(path, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

async function apiDelete(path: string): Promise<void> {
  const res = await request(path, { method: "DELETE" });
  if (res.status !== 204) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
}

// ── Auth ──

export const authApi = {
  register: (email: string, password: string, name?: string) =>
    apiFetch<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, name: name || null }),
    }),

  login: (email: string, password: string) =>
    apiFetch<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: (refreshToken: string) =>
    apiFetch<void>("/auth/logout", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};

export interface SuggestionsResponse {
  wardrobe_matches: SuggestionMatch[];
  shop_matches: ShopLink[];
}

export interface SuggestionMatch {
  id: number;
  name: string | null;
  category: string;
  color: string | null;
  pattern: string | null;
  image_url: string | null;
  color_harmony_score: number;
}

export interface ShopLink {
  store: string;
  url: string;
}

export const clothingApi = {
  list: (params?: { category?: string; season?: string; occasion_tag?: string; target_gender?: string }) => {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.season) query.set("season", params.season);
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    const qs = query.toString();
    return apiFetch<ClothingItem[]>(`/clothing/${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => apiFetch<ClothingItem>(`/clothing/${id}`),
  create: (item: Partial<ClothingItem>) =>
    apiFetch<ClothingItem>("/clothing/", {
      method: "POST",
      body: JSON.stringify(item),
    }),
  update: (id: number, item: Partial<ClothingItem>) =>
    apiFetch<ClothingItem>(`/clothing/${id}`, {
      method: "PUT",
      body: JSON.stringify(item),
    }),
  delete: (id: number) =>
    apiFetch<{ detail: string }>(`/clothing/${id}`, { method: "DELETE" }),
  suggestions: (id: number, category: string, limit?: number) => {
    const params = new URLSearchParams();
    params.set("category", category);
    if (limit) params.set("limit", String(limit));
    return apiFetch<SuggestionsResponse>(`/clothing/${id}/suggestions?${params.toString()}`);
  },
};

export const usersApi = {
  me: () => apiFetch<User>("/users/me"),
  setBodyType: (bodyType: string) =>
    apiFetch<User>("/users/me/body-type", {
      method: "POST",
      body: JSON.stringify({ body_type: bodyType }),
    }),
};

export const consentApi = {
  getStatus: () => apiFetch<ConsentStatus>("/users/me/consent"),

  giveConsent: () =>
    apiFetch<ConsentStatus>("/users/me/consent", {
      method: "POST",
      body: JSON.stringify({ consent_version: CURRENT_CONSENT_VERSION }),
    }),

  setPhoto: (imageUrl: string) =>
    apiFetch<User>("/users/me/photo", {
      method: "PUT",
      body: JSON.stringify({ image_url: imageUrl }),
    }),

  deletePhoto: () => apiDelete("/users/me/photo"),
};

export interface TagResult {
  category: string | null;
  subcategory: string | null;
  dominant_color: string | null;
  pattern: string | null;
  occasion_tag: string | null;
  season: string | null;
  fabric_type: string | null;
  fit_type: string | null;
  sleeve_length: string | null;
  garment_length: string | null;
  embellishments: string | null;
  target_gender: string | null;
  formality_score: number | null;
  _confidence: Record<string, number>;
  _needs_review: Record<string, boolean>;
  _error?: string;
}

export interface OutfitItem {
  id: number;
  name: string | null;
  category: string;
  color: string | null;
  pattern: string | null;
  fabric_type: string | null;
  fit_type: string | null;
  sleeve_length: string | null;
  image_url: string | null;
  target_gender: string | null;
}

export interface OutfitSuggestion {
  items: OutfitItem[];
  score: number;
  reason: string;
  breakdown: Record<string, number>;
}

export interface SmartOutfitResponse {
  query: string;
  params: {
    occasion_tag: string | null;
    formality_level: number | null;
    season: string | null;
    target_gender: string | null;
    vibe: string | null;
    source: string;
  };
  confidence: "high" | "medium" | "low";
  outfits: OutfitSuggestion[];
}

export interface WeatherInfo {
  city: string;
  temp_c: number;
  condition: string;
  humidity: number | null;
  icon: string | null;
}

export interface WeatherOutfitResponse {
  weather: WeatherInfo | null;
  guidance: { season: string; fabrics: string[] } | null;
  outfit: OutfitSuggestion | null;
  message: string | null;
}

export interface CapsuleItem {
  id: number;
  name: string | null;
  category: string;
  color: string | null;
  pattern: string | null;
  image_url: string | null;
  outfit_count: number;
}

export interface CapsuleResponse {
  items: CapsuleItem[];
  total_outfits: number;
  pair_count: number;
  categories: Record<string, number>;
  wardrobe_size: number;
}

export const outfitApi = {
  suggest: (params?: { occasion_tag?: string; target_gender?: string; limit?: number; offset?: number }) => {
    const query = new URLSearchParams();
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));
    return apiFetch<{ outfits: OutfitSuggestion[]; total: number }>(`/outfit-suggestions?${query.toString()}`);
  },

  smartSuggest: (query: string, limit = 5) =>
    apiFetch<SmartOutfitResponse>("/smart-outfit", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),

  weatherSuggest: (city?: string) => {
    const params = new URLSearchParams();
    if (city) params.set("city", city);
    return apiFetch<WeatherOutfitResponse>(`/weather-outfit?${params.toString()}`);
  },

  buildCapsule: (params?: {
    target_item_count?: number;
    occasion_tag?: string | null;
    locked_item_ids?: number[];
  }) =>
    apiFetch<CapsuleResponse>("/capsule-wardrobe", {
      method: "POST",
      body: JSON.stringify({
        target_item_count: params?.target_item_count ?? 20,
        occasion_tag: params?.occasion_tag ?? null,
        locked_item_ids: params?.locked_item_ids ?? [],
      }),
    }),
};

export interface OutfitFeedback {
  id: number;
  user_id: number;
  outfit_item_ids: number[];
  liked: boolean;
  created_at: string;
}

export const feedbackApi = {
  create: (outfitItemIds: number[], liked: boolean) =>
    apiFetch<OutfitFeedback>("/outfit-feedback", {
      method: "POST",
      body: JSON.stringify({ outfit_item_ids: outfitItemIds, liked }),
    }),
};

export interface ShoppingProduct {
  name: string;
  image_url: string;
  price: number;
  currency: string;
  affiliate_link: string;
  source: string;
}

export interface ShoppingGroup {
  gap_reason: string;
  missing_category: string;
  search_query: string;
  products: ShoppingProduct[];
}

export interface ClosetGap {
  missing_category: string;
  reason: string;
  search_query: string;
  shopping_links: ShopLink[];
}

export const shoppingApi = {
  suggest: (params?: { target_gender?: string; occasion_tag?: string }) => {
    const query = new URLSearchParams();
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    return apiFetch<ShoppingGroup[]>(`/shopping-suggestions?${query.toString()}`);
  },

  gaps: (targetGender?: string) => {
    const query = new URLSearchParams();
    if (targetGender) query.set("target_gender", targetGender);
    return apiFetch<ClosetGap[]>(`/closet-gaps?${query.toString()}`);
  },
};

export interface StyleMatchItem {
  name: string;
  match_percentage: number;
  reason: string;
  owned: boolean;
  item_id: number | null;
  category: string | null;
  color: string | null;
  image_url: string | null;
}

export interface ShoppingLink {
  store: string;
  url: string;
}

export interface ShoppingSuggestion {
  category: string;
  item_name: string;
  match_percentage: number;
  reason: string;
  owned: boolean;
  shopping_links: ShoppingLink[];
}

export interface OccasionOutfit {
  name: string;
  based_on: string;
}

export interface StyleMatchResponse {
  selectedItem: Record<string, any>;
  matchingBottoms: StyleMatchItem[];
  matchingTops: StyleMatchItem[];
  matchingFootwear: StyleMatchItem[];
  matchingAccessories: StyleMatchItem[];
  layeringSuggestions: StyleMatchItem[];
  recommendedColors: string[];
  avoidColors: string[];
  occasionOutfits: OccasionOutfit[];
  shoppingSuggestions: ShoppingSuggestion[];
  alreadyOwned: StyleMatchItem[];
}

export const styleMatchApi = {
  get: (itemId: number, limit?: number) =>
    apiFetch<StyleMatchResponse>(
      `/style-match?item_id=${itemId}${limit ? `&limit=${limit}` : ""}`
    ),
};

export interface ShopMatchProduct {
  name: string;
  image_url: string;
  price: number;
  currency: string;
  affiliate_link: string;
  source: string;
  similarity_score: number | null;
  fit_type?: string | null;
}

export interface ShopMatchGroup {
  label: string;
  ai_top_picks: ShopMatchProduct[];
  flipkart_products: ShopMatchProduct[];
  amazon_products: ShopMatchProduct[];
  meesho_search_link: ShopMatchProduct | null;
}

export const shopMatchApi = {
  get: (itemId: number, refresh = false) => {
    const query = refresh ? "?refresh=true" : "";
    return apiFetch<ShopMatchGroup[]>(`/items/${itemId}/shop-matches${query}`);
  },
};

export interface CalendarEntry {
  id: number;
  user_id: number;
  date: string;
  occasion_tag: string | null;
  locked_outfit_id: number | null;
  try_on_result_id: number | null;
  try_on_result_image_url: string | null;
  created_at: string;
}

export const calendarApi = {
  list: (params?: { start_date?: string; end_date?: string }) => {
    const query = new URLSearchParams();
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    return apiFetch<CalendarEntry[]>(`/calendar-entries/?${query.toString()}`);
  },
  create: (entry: { date: string; occasion_tag?: string }) =>
    apiFetch<CalendarEntry>("/calendar-entries/", {
      method: "POST",
      body: JSON.stringify(entry),
    }),
  update: (id: number, updates: { occasion_tag?: string; locked_outfit_id?: number | null }) =>
    apiFetch<CalendarEntry>(`/calendar-entries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  linkTryOnImage: (entryId: number, tryOnResultId: number) =>
    apiFetch<CalendarEntry>(`/calendar-entries/${entryId}/try-on-image`, {
      method: "PATCH",
      body: JSON.stringify({ try_on_result_id: tryOnResultId }),
    }),
};

export interface SuggestionWithProducts {
  suggestion: string;
  products: ShoppingProduct[];
}

export interface StyleAdviceResponse {
  shoes: SuggestionWithProducts[];
  accessories: SuggestionWithProducts[];
  layering: SuggestionWithProducts[];
  reasoning: string;
}

export const styleAdviceApi = {
  get: (itemId: number) =>
    apiFetch<StyleAdviceResponse>(`/style-advice?item_id=${itemId}`),

  explain: (outfitItemIds: number[]) =>
    apiFetch<{ explanation: string }>("/explain-outfit", {
      method: "POST",
      body: JSON.stringify({ outfit_item_ids: outfitItemIds }),
    }),
};

export interface PackingGroup {
  category: string;
  quantity: number;
  note: string;
}

export interface PackingItem {
  id: number;
  name: string | null;
  category: string;
  color: string | null;
  image_url: string | null;
  note: string;
}

export interface PackingMissingGroup {
  category: string;
  quantity_needed: number;
  note: string;
  search_query: string;
  shopping_links: ShopLink[];
}

export interface PackingList {
  destination: string;
  duration: number;
  purpose: string;
  weather_note: string;
  tips: string[];
  groups: PackingGroup[];
  selected_items: PackingItem[];
  missing_groups: PackingMissingGroup[];
  ai_backed: boolean;
}

export const packingApi = {
  purposes: () => apiFetch<{ purposes: string[] }>("/packing/purposes"),

  generate: (destination: string, duration: number, purpose: string) =>
    apiFetch<PackingList>("/packing/packing-list", {
      method: "POST",
      body: JSON.stringify({ destination, duration, purpose }),
    }),
};

export interface RatingScore {
  score: number;
  reason: string;
}

export interface FashionRating {
  available: boolean;
  message?: string;
  scores?: Record<string, RatingScore>;
  average_score?: number;
  suggestions?: string[];
  vibe_tags?: string[];
  primary_colors_detected?: string[];
}

export const fashionRatingApi = {
  rate: (imageUrl?: string) =>
    apiFetch<FashionRating>("/fashion-rating/rate", {
      method: "POST",
      body: JSON.stringify({ image_url: imageUrl ?? null }),
    }),
};

export interface WornItem {
  id: number;
  name: string | null;
  category: string;
  color: string | null;
  image_url: string | null;
  wear_count: number;
}

export interface WearAnalytics {
  days: number;
  total_wears: number;
  items_worn: number;
  wardrobe_size: number;
  most_worn: WornItem[];
  never_worn: WornItem[];
}

export interface RepeatWarning {
  item_id: number;
  item_name: string;
  category: string | null;
  wear_count: number;
  message: string;
  alternative: WornItem | null;
}

export interface RepeatCheck {
  days: number;
  threshold: number;
  warnings: RepeatWarning[];
}

export const wearApi = {
  analytics: (days = 30) =>
    apiFetch<WearAnalytics>(`/calendar/analytics?days=${days}`),

  repeatCheck: (itemIds: number[], days = 30) =>
    apiFetch<RepeatCheck>(
      `/calendar/repeat-check?days=${days}` +
        `&outfit_item_ids=${itemIds.join(",")}`,
    ),
};

export interface TryOnJob {
  id: number;
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  result_image_url: string | null;
  error_message: string | null;
  error_type: "bad_photo" | "provider_error" | "rate_limit" | null;
  model_used: string | null;
  latency_ms: number | null;
  created_at: string;
  rate_limit_remaining?: number | null;
  rate_limit_limit?: number | null;
  rate_limit_resets_at?: string | null;
}

export interface TryOnRateLimitError {
  error: string;
  message: string;
  limit: number;
  used: number;
  resets_at: string;
}

export interface TryOnUsage {
  used: number;
  limit: number;
  remaining: number;
  resets_at: string;
}

export const tryOnApi = {
  render: async (garmentIds: number[]): Promise<TryOnJob> => {
    const res = await request("/try-on", {
      method: "POST",
      body: JSON.stringify({ garment_ids: garmentIds }),
    });
    if (res.status === 429) {
      const body = await res.json();
      const detail = body?.detail || {};
      const err = new Error(detail.message || "Daily try-on limit exceeded");
      (err as any).rateLimit = {
        error: detail.error || "rate_limit_exceeded",
        message: detail.message || "Daily try-on limit exceeded",
        limit: detail.limit || 0,
        used: detail.used || 0,
        resets_at: detail.resets_at || "",
      } as TryOnRateLimitError;
      throw err;
    }
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`API error ${res.status}: ${text}`);
    }
    return res.json();
  },

  poll: (jobId: string) =>
    apiFetch<TryOnJob>(`/try-on/${jobId}`),

  results: () => apiFetch<TryOnJob[]>("/try-on/results"),

  usage: () => apiFetch<TryOnUsage>("/try-on/usage"),
};

export const uploadApi = {
  uploadImage: async (fileUri: string, fileName: string, mimeType: string) => {
    const formData = new FormData();
    formData.append("file", {
      uri: fileUri,
      name: fileName,
      type: mimeType,
    } as any);
    const res = await request("/upload-image", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<{ image_url: string }>;
  },

  uploadImageWithProgress: (
    fileUri: string,
    fileName: string,
    mimeType: string,
    onProgress?: (progress: number) => void,
  ): Promise<{ image_url: string }> => {
    return new Promise(async (resolve, reject) => {
      const formData = new FormData();
      formData.append("file", {
        uri: fileUri,
        name: fileName,
        type: mimeType,
      } as any);

      const xhrUpload = (authToken: string) =>
        new Promise<{ image_url: string }>((res, rej) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", `${BASE_URL}/upload-image`);
          xhr.setRequestHeader("Authorization", `Bearer ${authToken}`);

          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable && onProgress) {
              onProgress(e.loaded / e.total);
            }
          };

          xhr.onload = () => {
            if (xhr.status === 200) {
              try {
                res(JSON.parse(xhr.responseText));
              } catch {
                rej(new Error("Invalid server response"));
              }
            } else if (xhr.status === 401) {
              const err = new Error("Unauthorized") as Error & { status: number };
              err.status = 401;
              rej(err);
            } else {
              rej(new Error(`Upload failed (${xhr.status})`));
            }
          };

          xhr.onerror = () => rej(new Error("Network error during upload"));
          xhr.send(formData);
        });

      try {
        const token = await getValidAccessToken();
        if (!token) {
          await clearTokens();
          notifyAuthExpired();
          reject(new Error("Not authenticated"));
          return;
        }
        try {
          resolve(await xhrUpload(token));
        } catch (err) {
          if ((err as Error & { status?: number }).status === 401) {
            const newToken = await refreshAccessToken();
            if (newToken) {
              resolve(await xhrUpload(newToken));
              return;
            }
            await clearTokens();
            notifyAuthExpired();
          }
          reject(err);
        }
      } catch (err) {
        reject(err);
      }
    });
  },

  tagItem: (imageUrl: string) =>
    apiFetch<TagResult>("/tag-item", {
      method: "POST",
      body: JSON.stringify({ image_url: imageUrl }),
    }),
};
