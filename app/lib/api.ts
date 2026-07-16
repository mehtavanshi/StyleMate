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
  style_preference: string | null;
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
  list: (params?: { category?: string; season?: string; occasion_tag?: string }) => {
    const query = new URLSearchParams();
    query.set("user_id", String(DEMO_USER_ID));
    if (params?.category) query.set("category", params.category);
    if (params?.season) query.set("season", params.season);
    if (params?.occasion_tag) query.set("occasion_tag", params.occasion_tag);
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
};
