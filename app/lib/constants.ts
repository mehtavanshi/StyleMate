export const DEMO_USER_ID = 1;
export const CURRENT_CONSENT_VERSION = "1.0";

/** Resolve a photo URL that may be relative (local) or absolute (S3/GCS signed). */
export function resolvePhotoUrl(url: string | null, baseUrl: string): string | null {
  if (!url) return null;
  return url.startsWith("http://") || url.startsWith("https://") ? url : `${baseUrl}${url}`;
}

/** Resolve any image URL — same logic as resolvePhotoUrl, for generic use. */
export function resolveImageUrl(url: string | null, baseUrl: string): string | null {
  if (!url) return null;
  return url.startsWith("http://") || url.startsWith("https://") ? url : `${baseUrl}${url}`;
}

// Photo capture validation
export const MIN_SHORT_EDGE_PX = 768;
export const MAX_LONG_EDGE_PX = 1600;
export const JPEG_QUALITY = 0.85;
/**
 * Resize spec that constrains the **long** edge. `{ width: MAX }` alone leaves
 * a portrait photo's height unbounded, so tall images uploaded full-size.
 * Returns null when the image is already small enough (never upscale).
 */
export function longEdgeResize(
  width: number,
  height: number,
): { width: number } | { height: number } | null {
  const longEdge = Math.max(width || 0, height || 0);
  if (!longEdge || longEdge <= MAX_LONG_EDGE_PX) return null;
  return width >= height ? { width: MAX_LONG_EDGE_PX } : { height: MAX_LONG_EDGE_PX };
}

export const MIN_BLUR_THRESHOLD = 80;
export const MIN_BRIGHTNESS = 40;
export const MIN_PERSON_CONFIDENCE = 0.5;
export const MIN_BODY_HEIGHT_RATIO = 0.6;
