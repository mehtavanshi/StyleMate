import { useWindowDimensions } from "react-native";

/**
 * Column count for card grids: 2 on phones, more as the screen widens so
 * tablet cards stay card-sized instead of stretching to half the screen.
 */
export function useGridColumns(): number {
  const { width } = useWindowDimensions();
  if (width >= 1000) return 4;
  if (width >= 700) return 3;
  return 2;
}

/**
 * Pads a list with nulls so the final row is full — with `flex: 1` cells a
 * lone trailing card would otherwise stretch across the whole row.
 */
export function padToRows<T>(items: T[], columns: number): (T | null)[] {
  const remainder = items.length % columns;
  if (remainder === 0) return items;
  return [...items, ...Array<null>(columns - remainder).fill(null)];
}
