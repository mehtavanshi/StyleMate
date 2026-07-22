import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { NativeModules } from "react-native";

import {
  MIN_BLUR_THRESHOLD,
  MIN_BRIGHTNESS,
  MIN_PERSON_CONFIDENCE,
  MIN_BODY_HEIGHT_RATIO,
  MIN_SHORT_EDGE_PX,
} from "./constants";

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

let _MLKit: any = false;

const MLKIT_NATIVE_MODULE = "RNMLKitObjectDetection";

function getMLKit(): any {
  if (_MLKit !== false) return _MLKit;
  if (!NativeModules[MLKIT_NATIVE_MODULE]) return false;
  try {
    _MLKit = require("@infinitered/react-native-mlkit-object-detection");
  } catch {
    _MLKit = false;
  }
  return _MLKit;
}

function computeLaplacianVariance(pixels: Uint8Array, w: number, h: number): number {
  const gray = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const r = pixels[i * 4];
    const g = pixels[i * 4 + 1];
    const b = pixels[i * 4 + 2];
    gray[i] = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
  }

  const laplacian: number[] = [];
  const kernel = [0, 1, 0, 1, -4, 1, 0, 1, 0];

  for (let y = 1; y < h - 1; y++) {
    for (let x = 1; x < w - 1; x++) {
      let sum = 0;
      for (let ky = -1; ky <= 1; ky++) {
        for (let kx = -1; kx <= 1; kx++) {
          const idx = (y + ky) * w + (x + kx);
          sum += gray[idx] * kernel[(ky + 1) * 3 + (kx + 1)];
        }
      }
      laplacian.push(sum);
    }
  }

  const mean = laplacian.reduce((a, b) => a + b, 0) / laplacian.length;
  const variance = laplacian.reduce((a, b) => a + (b - mean) ** 2, 0) / laplacian.length;
  return variance;
}

function computeAverageBrightness(pixels: Uint8Array, w: number, h: number): number {
  let sum = 0;
  for (let i = 0; i < w * h; i++) {
    const r = pixels[i * 4];
    const g = pixels[i * 4 + 1];
    const b = pixels[i * 4 + 2];
    sum += 0.299 * r + 0.587 * g + 0.114 * b;
  }
  return sum / (w * h);
}

async function getThumbnailBase64(uri: string): Promise<string> {
  const manipulator = ImageManipulator.manipulate(uri);
  const rendered = await manipulator.renderAsync();
  const result = await rendered.saveAsync({
    compress: 0.9,
    format: SaveFormat.JPEG,
    base64: true,
  });
  return result.base64!;
}

async function checkBlurAndBrightness(uri: string): Promise<string[]> {
  const errors: string[] = [];
  try {
    const base64 = await getThumbnailBase64(uri);
    const binaryStr = atob(base64);
    const bytes = new Uint8Array(binaryStr.length);
    for (let i = 0; i < binaryStr.length; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }

    if (base64.length < 100) {
      errors.push("Could not analyze image quality");
      return errors;
    }

    const w = 100;
    const h = Math.round(bytes.length / 4 / w);

    const variance = computeLaplacianVariance(bytes, w, h);
    if (variance < MIN_BLUR_THRESHOLD) {
      errors.push("Image is too blurry — try better lighting or hold steady");
    }

    const brightness = computeAverageBrightness(bytes, w, h);
    if (brightness < MIN_BRIGHTNESS) {
      errors.push("Image is too dark — move to a brighter area");
    }
  } catch {
    errors.push("Could not analyze image quality");
  }
  return errors;
}

let _modelName: string | null = null;

async function getModel(): Promise<string | null> {
  const MLKit = getMLKit();
  if (!MLKit) return null;
  if (!_modelName) {
    _modelName = await MLKit.loadDefaultModel({
      shouldEnableClassification: true,
      shouldEnableMultipleObjects: true,
      detectorMode: "singleImage",
    });
  }
  return _modelName;
}

async function checkBodyDetection(uri: string, imageHeight: number): Promise<string[]> {
  const errors: string[] = [];
  const MLKit = getMLKit();
  if (!MLKit) return errors;
  try {
    const modelName = await getModel();
    if (!modelName) {
      errors.push("Body detection not available");
      return errors;
    }
    const objects = await MLKit.detectObjects(modelName, uri);

    const persons = objects.filter((o: any) => {
      const personLabel = (o.labels || []).find(
        (l: any) =>
          (l.text || "").toLowerCase() === "person" &&
          l.confidence >= MIN_PERSON_CONFIDENCE,
      );
      return !!personLabel;
    });

    if (persons.length === 0) {
      errors.push("No person detected — stand in front of the camera");
      return errors;
    }

    if (persons.length > 1) {
      errors.push("Multiple people detected — only you should be in frame");
      return errors;
    }

    const bbox = persons[0].frame;
    const bodyHeight = bbox.size?.y ?? 0;
    if (bodyHeight / imageHeight < MIN_BODY_HEIGHT_RATIO) {
      errors.push("Step back so your whole body is visible head to toe");
    }
  } catch {
    errors.push("Could not detect body position — please try again");
  }
  return errors;
}

export async function validateImage(
  uri: string,
  width: number,
  height: number,
  includeBodyCheck = true,
): Promise<ValidationResult> {
  const errors: string[] = [];

  const shortEdge = Math.min(width, height);
  if (shortEdge < MIN_SHORT_EDGE_PX) {
    errors.push(`Image too small (${MIN_SHORT_EDGE_PX}px minimum on short edge)`);
  }

  const qualityErrors = await checkBlurAndBrightness(uri);
  errors.push(...qualityErrors);

  if (includeBodyCheck) {
    const bodyErrors = await checkBodyDetection(uri, height);
    errors.push(...bodyErrors);
  }

  return { valid: errors.length === 0, errors };
}
