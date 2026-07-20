import { BASE_URL } from "../config/api";

export interface ClothingItem {
  id: number;
  user_id: number;
  name: string | null;
  category: string;
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
  formality_score: number | null;
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
  created_at: string;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

const DEMO_USER_ID = 1;

export const clothingApi = {
  list: (params?: { category?: string; season?: string; occasion_tag?: string; target_gender?: string }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.category) query.set("category", params.category);
    if (params?.season) query.set("season", params.season);
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    return apiFetch<ClothingItem[]>(`/clothing/?${query.toString()}`);
  },
  get: (id: number) => apiFetch<ClothingItem>(`/clothing/${id}`),
  create: (item: Partial<ClothingItem>) =>
    apiFetch<ClothingItem>("/clothing/", {
      method: "POST",
      body: JSON.stringify({ ...item, user_id: DEMO_USER_ID }),
    }),
  update: (id: number, item: Partial<ClothingItem>) =>
    apiFetch<ClothingItem>(`/clothing/${id}`, {
      method: "PUT",
      body: JSON.stringify(item),
    }),
  delete: (id: number) =>
    apiFetch<{ detail: string }>(`/clothing/${id}`, { method: "DELETE" }),
};

export const usersApi = {
  get: (id: number) => apiFetch<User>(`/users/${id}`),
  setBodyType: (id: number, bodyType: string) =>
    apiFetch<User>(`/users/${id}/body-type`, {
      method: "POST",
      body: JSON.stringify({ body_type: bodyType }),
    }),
};

export interface TagResult {
  category: string | null;
  dominant_color: string | null;
  pattern: string | null;
  occasion_tag: string | null;
  season: string | null;
  fabric_type: string | null;
  fit_type: string | null;
  sleeve_length: string | null;
  target_gender: string | null;
  formality_score: number | null;
  _confidence: Record<string, number>;
  _needs_review: Record<string, boolean>;
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

export const outfitApi = {
  suggest: (params?: { occasion_tag?: string; target_gender?: string; limit?: number }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    if (params?.limit) query.set("limit", String(params.limit));
    return apiFetch<OutfitSuggestion[]>(`/outfit-suggestions?${query.toString()}`);
  },
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
      body: JSON.stringify({ user_id: DEMO_USER_ID, outfit_item_ids: outfitItemIds, liked }),
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

export const shoppingApi = {
  suggest: (params?: { target_gender?: string; occasion_tag?: string }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.target_gender) query.set("target_gender", params.target_gender);
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
    return apiFetch<ShoppingGroup[]>(`/shopping-suggestions?${query.toString()}`);
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
  get: (itemId: number) =>
    apiFetch<StyleMatchResponse>(`/style-match?item_id=${itemId}`),
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
  created_at: string;
}

export const calendarApi = {
  list: (params?: { start_date?: string; end_date?: string }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    return apiFetch<CalendarEntry[]>(`/calendar-entries/?${query.toString()}`);
  },
  create: (entry: { date: string; occasion_tag?: string }) =>
    apiFetch<CalendarEntry>("/calendar-entries/", {
      method: "POST",
      body: JSON.stringify({ ...entry, user_id: DEMO_USER_ID }),
    }),
  update: (id: number, updates: { occasion_tag?: string; locked_outfit_id?: number | null }) =>
    apiFetch<CalendarEntry>(`/calendar-entries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
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
};

export const uploadApi = {
  uploadImage: async (fileUri: string, fileName: string, mimeType: string) => {
    const formData = new FormData();
    formData.append("file", {
      uri: fileUri,
      name: fileName,
      type: mimeType,
    } as any);
    const res = await fetch(`${BASE_URL}/upload-image`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload API error ${res.status}: ${await res.text()}`);
    return res.json() as Promise<{ image_url: string }>;
  },

  tagItem: (imageUrl: string) =>
    apiFetch<TagResult>("/tag-item", {
      method: "POST",
      body: JSON.stringify({ image_url: imageUrl }),
    }),
};
