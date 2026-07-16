import { Platform } from "react-native";

const BASE_URL = Platform.select({
  android: "http://10.30.1.21:8000",
  ios: "http://127.0.0.1:8000",
  web: "http://10.0.15.133:8000",
  default: "http://10.0.15.133:8000",
});

export { BASE_URL };
