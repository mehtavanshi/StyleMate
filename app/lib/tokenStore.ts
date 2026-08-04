import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

import type { User } from "./api";

export const ACCESS_TOKEN_KEY = "sm_access_token";
export const REFRESH_TOKEN_KEY = "sm_refresh_token";
export const USER_KEY = "sm_user";

const isNative = Platform.OS !== "web";

async function getItem(key: string): Promise<string | null> {
  if (!isNative) {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  }
  return SecureStore.getItemAsync(key);
}

async function setItem(key: string, value: string): Promise<void> {
  if (!isNative) {
    try {
      window.localStorage.setItem(key, value);
      return;
    } catch {
      return;
    }
  }
  await SecureStore.setItemAsync(key, value);
}

async function deleteItem(key: string): Promise<void> {
  if (!isNative) {
    try {
      window.localStorage.removeItem(key);
      return;
    } catch {
      return;
    }
  }
  await SecureStore.deleteItemAsync(key);
}

export async function getAccessToken(): Promise<string | null> {
  return getItem(ACCESS_TOKEN_KEY);
}

export async function getRefreshToken(): Promise<string | null> {
  return getItem(REFRESH_TOKEN_KEY);
}

export async function getStoredUser(): Promise<User | null> {
  const raw = await getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export async function setTokens(accessToken: string, refreshToken: string): Promise<void> {
  await Promise.all([
    setItem(ACCESS_TOKEN_KEY, accessToken),
    setItem(REFRESH_TOKEN_KEY, refreshToken),
  ]);
}

export async function setStoredUser(user: User): Promise<void> {
  await setItem(USER_KEY, JSON.stringify(user));
}

export async function clearTokens(): Promise<void> {
  await Promise.all([
    deleteItem(ACCESS_TOKEN_KEY),
    deleteItem(REFRESH_TOKEN_KEY),
    deleteItem(USER_KEY),
  ]);
}
