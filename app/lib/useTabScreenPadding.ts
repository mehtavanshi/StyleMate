import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useBottomTabBarHeight } from "@react-navigation/bottom-tabs";
import { spacing } from "../theme/tokens";

export function useTabScreenPadding(headerHeight = 0) {
  const insets = useSafeAreaInsets();
  const tabBarHeight = useBottomTabBarHeight();
  return {
    paddingTop: headerHeight,
    paddingBottom: tabBarHeight + insets.bottom + spacing.lg,
  };
}
