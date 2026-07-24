import { Platform } from "react-native";

const BASE_URL =
  Platform.select({
    android: process.env.EXPO_PUBLIC_API_ANDROID,
    ios: process.env.EXPO_PUBLIC_API_IOS,
    web: process.env.EXPO_PUBLIC_API_WEB,
    default: process.env.EXPO_PUBLIC_API_DEFAULT,
  }) ?? "http://10.147.203.215:8000";

export { BASE_URL };
