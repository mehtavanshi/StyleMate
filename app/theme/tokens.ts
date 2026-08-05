import type { TextStyle, ViewStyle } from "react-native";

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
} as const;

export const fontSize = {
  xs: 12,
  sm: 14,
  base: 16,
  lg: 18,
  xl: 20,
  xxl: 24,
  xxxl: 32,
  display: 48,
} as const;

export const fontWeight = {
  semibold: "600" as const,
  bold: "700" as const,
  extrabold: "800" as const,
};

export const borderRadius = {
  sm: 6,
  md: 10,
  lg: 16,
  full: 9999,
} as const;

export const shadow: Record<string, ViewStyle> = {
  sm: {
    boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
    elevation: 2,
  },
  md: {
    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
    elevation: 3,
  },
};

export const MIN_TOUCH_TARGET = 44;

export const colors = {
  background: "#f5f5f5",
  surface: "#fff",
  // Inputs, chips and other inset controls sitting on `surface`. One token so
  // a search box and the chips beneath it can't drift to different greys.
  surfaceSunken: "#ededed",
  border: "#eee",
  text: {
    primary: "#222",
    secondary: "#777",
    tertiary: "#888",
    muted: "#aaa",
    light: "#999",
    white: "#fff",
  },
  accent: "#333",
  success: "#2ECC71",
  warning: "#E8A317",
  danger: "#E74C3C",
  score: {
    high: "#2ECC71",
    mid: "#E8A317",
    low: "#E74C3C",
  },
};

export const typography: Record<string, TextStyle> = {
  h1: { fontSize: fontSize.xl, fontWeight: fontWeight.extrabold },
  h2: { fontSize: fontSize.lg, fontWeight: fontWeight.bold },
  h3: { fontSize: fontSize.base, fontWeight: fontWeight.semibold },
  body: { fontSize: fontSize.sm, fontWeight: "400" },
  caption: { fontSize: fontSize.xs, fontWeight: "400" },
};
