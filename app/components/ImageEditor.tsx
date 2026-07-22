import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Image,
  LayoutChangeEvent,
  PanResponder,
  PanResponderGestureState,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { borderRadius as br, colors, fontSize, fontWeight, spacing } from "../theme/tokens";

const HANDLE_HIT = 32;
const MIN_CROP_NORMALIZED = 0.05;

interface CropRect {
  x: number; y: number; w: number; h: number;
}

interface Props {
  uri: string;
  imageWidth: number;
  imageHeight: number;
  onApply: (newUri: string, newWidth: number, newHeight: number) => void;
  onCancel: () => void;
}

export default function ImageEditor({ uri: initialUri, imageWidth: initialW, imageHeight: initialH, onApply, onCancel }: Props) {
  const [busy, setBusy] = useState(false);
  const [currentUri, setCurrentUri] = useState(initialUri);
  const [imgW, setImgW] = useState(initialW);
  const [imgH, setImgH] = useState(initialH);
  const [rotationCount, setRotationCount] = useState(0);

  const dispW = rotationCount % 2 === 0 ? imgW : imgH;
  const dispH = rotationCount % 2 === 0 ? imgH : imgW;

  const [layout, setLayout] = useState({ w: 0, h: 0 });

  const scaleX = layout.w / dispW;
  const scaleY = layout.h / dispH;
  const drawScale = Math.min(scaleX, scaleY);
  const drawOffX = (layout.w - dispW * drawScale) / 2;
  const drawOffY = (layout.h - dispH * drawScale) / 2;

  const [crop, setCrop] = useState<CropRect>({ x: 0, y: 0, w: 1, h: 1 });

  const cropRef = useRef(crop);
  cropRef.current = crop;
  const startCropRef = useRef<CropRect | null>(null);
  const handleRef = useRef<string | null>(null);
  const paramsRef = useRef({ drawScale, drawOffX, drawOffY, dispW, dispH });
  paramsRef.current = { drawScale, drawOffX, drawOffY, dispW, dispH };

  const displayCX = crop.x * dispW * drawScale + drawOffX;
  const displayCY = crop.y * dispH * drawScale + drawOffY;
  const displayCW = crop.w * dispW * drawScale;
  const displayCH = crop.h * dispH * drawScale;

  const toImg = useCallback((lx: number, ly: number) => {
    const p = paramsRef.current;
    return {
      x: Math.max(0, Math.min(1, (lx - p.drawOffX) / (p.dispW * p.drawScale))),
      y: Math.max(0, Math.min(1, (ly - p.drawOffY) / (p.dispH * p.drawScale))),
    };
  }, []);

  const pan = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (evt) => {
        const { locationX, locationY } = evt.nativeEvent;
        const c = cropRef.current;
        const p = paramsRef.current;
        const cx = c.x * p.dispW * p.drawScale + p.drawOffX;
        const cy = c.y * p.dispH * p.drawScale + p.drawOffY;
        const cw = c.w * p.dispW * p.drawScale;
        const ch = c.h * p.dispH * p.drawScale;
        const h = HANDLE_HIT;

        const near = (tx: number, ty: number) =>
          Math.abs(locationX - tx) < h && Math.abs(locationY - ty) < h;

        if (near(cx, cy)) handleRef.current = "tl";
        else if (near(cx + cw, cy)) handleRef.current = "tr";
        else if (near(cx, cy + ch)) handleRef.current = "bl";
        else if (near(cx + cw, cy + ch)) handleRef.current = "br";
        else if (
          locationX >= cx && locationX <= cx + cw &&
          locationY >= cy && locationY <= cy + ch
        ) handleRef.current = "move";
        else handleRef.current = null;

        startCropRef.current = { ...c };
      },
      onPanResponderMove: (_, gs: PanResponderGestureState) => {
        const sc = startCropRef.current;
        const h = handleRef.current;
        if (!sc || !h) return;
        const p = paramsRef.current;
        const dx = gs.dx / (p.dispW * p.drawScale);
        const dy = gs.dy / (p.dispH * p.drawScale);
        const mn = MIN_CROP_NORMALIZED;
        let { x, y, w, h: hh } = sc;

        if (h === "move") {
          x = Math.max(0, Math.min(1 - w, sc.x + dx));
          y = Math.max(0, Math.min(1 - hh, sc.y + dy));
        } else if (h === "tl") {
          const nx = Math.max(0, Math.min(sc.x + sc.w - mn, sc.x + dx));
          const ny = Math.max(0, Math.min(sc.y + sc.h - mn, sc.y + dy));
          x = nx; y = ny;
          w = sc.w - (nx - sc.x);
          hh = sc.h - (ny - sc.y);
        } else if (h === "tr") {
          const ny = Math.max(0, Math.min(sc.y + sc.h - mn, sc.y + dy));
          w = Math.max(mn, Math.min(1 - sc.x, sc.w + dx));
          hh = sc.h - (ny - sc.y);
          y = ny;
        } else if (h === "bl") {
          const nx = Math.max(0, Math.min(sc.x + sc.w - mn, sc.x + dx));
          hh = Math.max(mn, Math.min(1 - sc.y, sc.h + dy));
          w = sc.w - (nx - sc.x);
          x = nx;
        } else if (h === "br") {
          w = Math.max(mn, Math.min(1 - sc.x, sc.w + dx));
          hh = Math.max(mn, Math.min(1 - sc.y, sc.h + dy));
        }

        setCrop({ x, y, w, h: hh });
      },
      onPanResponderRelease: () => {
        handleRef.current = null;
        startCropRef.current = null;
      },
    })
  ).current;

  const handleRotate = useCallback(async () => {
    setBusy(true);
    try {
      const result = await ImageManipulator.manipulate(currentUri)
        .rotate(90)
        .renderAsync();
      const saved = await result.saveAsync({ compress: 1, format: SaveFormat.JPEG });
      setCurrentUri(saved.uri);
      setImgW(saved.width);
      setImgH(saved.height);
      setCrop({ x: 0, y: 0, w: 1, h: 1 });
      setRotationCount((r) => r + 1);
    } catch {
      // fall through
    } finally {
      setBusy(false);
    }
  }, [currentUri]);

  const handleApplyCrop = useCallback(async () => {
    setBusy(true);
    try {
      const ox = Math.round(crop.x * imgW);
      const oy = Math.round(crop.y * imgH);
      const cw = Math.round(crop.w * imgW);
      const ch = Math.round(crop.h * imgH);
      const man = await ImageManipulator.manipulate(currentUri)
        .crop({ originX: ox, originY: oy, width: cw, height: ch })
        .renderAsync();
      const saved = await man.saveAsync({ compress: 1, format: SaveFormat.JPEG });
      onApply(saved.uri, saved.width, saved.height);
    } catch {
      onCancel();
    } finally {
      setBusy(false);
    }
  }, [currentUri, imgW, imgH, crop, onApply, onCancel]);

  const onLayout = useCallback((e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    setLayout({ w: width, h: height });
  }, []);

  if (busy) {
    return (
      <View style={styles.busy}>
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.busyText}>Processing image...</Text>
      </View>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity style={styles.headerBtn} onPress={onCancel}>
          <Text style={styles.headerBtnText}>Cancel</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Crop & Rotate</Text>
        <TouchableOpacity style={styles.headerBtn} onPress={handleApplyCrop}>
          <Text style={styles.headerBtnText}>Apply</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.imageArea} onLayout={onLayout}>
        <Image source={{ uri: currentUri }} style={styles.image} />
        {layout.w > 0 && (
          <View style={StyleSheet.absoluteFill} {...pan.panHandlers}>
            <View style={[StyleSheet.absoluteFill, styles.mask]}>
              <View style={[styles.clearRegion, { left: displayCX, top: displayCY, width: displayCW, height: displayCH }]} />
            </View>
            <View style={[styles.cropFrame, { left: displayCX, top: displayCY, width: displayCW, height: displayCH, borderColor: "#fff" }]}>
              <Corner cx={displayCX} cy={displayCY} />
              <Corner cx={displayCX + displayCW} cy={displayCY} />
              <Corner cx={displayCX} cy={displayCY + displayCH} />
              <Corner cx={displayCX + displayCW} cy={displayCY + displayCH} />
            </View>
          </View>
        )}
      </View>

      <View style={styles.footer}>
        <TouchableOpacity style={styles.rotateBtn} onPress={handleRotate}>
          <Text style={styles.rotateBtnText}>↻ Rotate 90°</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function Corner({ cx, cy }: { cx: number; cy: number }) {
  return (
    <View
      style={[styles.corner, { left: cx - 12, top: cy - 12 }]}
      pointerEvents="none"
    >
      <View style={styles.cornerInner} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  busy: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: "#000", gap: spacing.md },
  busyText: { color: colors.text.white, fontSize: fontSize.base },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm + 2,
    backgroundColor: "#111",
  },
  headerTitle: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.semibold },
  headerBtn: { paddingVertical: spacing.xs, paddingHorizontal: spacing.sm, minWidth: 60, alignItems: "center" },
  headerBtnText: { color: "#4A90D9", fontSize: fontSize.base, fontWeight: fontWeight.semibold },
  imageArea: { flex: 1, position: "relative" },
  image: { width: "100%", height: "100%", resizeMode: "contain" },
  mask: {
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  clearRegion: {
    backgroundColor: "transparent",
    position: "absolute",
  },
  cropFrame: {
    position: "absolute",
    borderWidth: 1.5,
  },
  corner: {
    position: "absolute",
    width: 24,
    height: 24,
    alignItems: "center",
    justifyContent: "center",
  },
  cornerInner: {
    width: 10,
    height: 10,
    borderWidth: 2,
    borderColor: "#fff",
    backgroundColor: "transparent",
  },
  footer: {
    flexDirection: "row",
    justifyContent: "center",
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.xl,
    backgroundColor: "#111",
    gap: spacing.md,
  },
  rotateBtn: {
    backgroundColor: "#333",
    borderRadius: br.md,
    paddingVertical: spacing.sm + 4,
    paddingHorizontal: spacing.xl,
  },
  rotateBtnText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.semibold },
});
