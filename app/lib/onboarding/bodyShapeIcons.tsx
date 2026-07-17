import * as React from "react";
import Svg, { Path } from "react-native-svg";
import type { BodyType } from "./scoreBodyType";

interface IconProps {
  size?: number;
  color?: string;
}

const DEFAULT_SIZE = 64;
const DEFAULT_COLOR = "#333";

export function RectangleIcon({ size = DEFAULT_SIZE, color = DEFAULT_COLOR }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Path
        d="M22 8 L42 8 L44 20 L40 56 L24 56 L20 20 Z"
        fill={color}
      />
    </Svg>
  );
}

export function HourglassIcon({ size = DEFAULT_SIZE, color = DEFAULT_COLOR }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Path
        d="M20 8 L44 8 L36 30 C34 34 30 34 28 30 L20 8 Z M28 34 L36 34 L44 56 L20 56 L28 34 Z"
        fill={color}
      />
    </Svg>
  );
}

export function PearIcon({ size = DEFAULT_SIZE, color = DEFAULT_COLOR }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Path
        d="M26 8 L38 8 L36 22 L46 50 C47 56 17 56 18 50 L28 22 Z"
        fill={color}
      />
    </Svg>
  );
}

export function AppleIcon({ size = DEFAULT_SIZE, color = DEFAULT_COLOR }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Path
        d="M16 26 C16 18 48 18 48 26 L44 44 C43 52 21 52 20 44 Z M26 8 L38 8 L38 18 L26 18 Z"
        fill={color}
      />
    </Svg>
  );
}

export function InvertedTriangleIcon({ size = DEFAULT_SIZE, color = DEFAULT_COLOR }: IconProps) {
  return (
    <Svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <Path
        d="M18 8 L46 8 L42 24 L34 56 L30 56 L22 24 Z"
        fill={color}
      />
    </Svg>
  );
}

export const BODY_TYPE_ICONS: Record<BodyType, (props: IconProps) => React.ReactElement> = {
  rectangle: RectangleIcon,
  hourglass: HourglassIcon,
  pear: PearIcon,
  apple: AppleIcon,
  inverted_triangle: InvertedTriangleIcon,
};
