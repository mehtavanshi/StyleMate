import { useEffect } from "react";
import { BackHandler } from "react-native";

/**
 * Registers an Android hardware back-button listener.
 * Return `true` from the callback to prevent the default behaviour
 * (React Navigation pop). Return `false` to let RN handle it normally.
 */
export default function useHardwareBack(handler: () => boolean) {
  useEffect(() => {
    const sub = BackHandler.addEventListener("hardwareBackPress", handler);
    return () => sub.remove();
  }, [handler]);
}
