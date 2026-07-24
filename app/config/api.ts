import { Platform } from "react-native";

const BASE_URL = Platform.select({
  android: process.env.EXPO_PUBLIC_API_ANDROID || "http://10.0.2.2:8000",
  ios: process.env.EXPO_PUBLIC_API_IOS || "http://127.0.0.1:8000",
  web: process.env.EXPO_PUBLIC_API_WEB || "http://127.0.0.1:8000",
  default: process.env.EXPO_PUBLIC_API_DEFAULT || "http://127.0.0.1:8000",
});

export { BASE_URL };
