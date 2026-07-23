import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { router, useLocalSearchParams, useNavigation } from "expo-router";

import { consentApi, DEMO_USER_ID, uploadApi } from "../lib/api";
import { MAX_LONG_EDGE_PX, JPEG_QUALITY } from "../lib/constants";
import { validateImage } from "../lib/imageValidation";
import ImageEditor from "../components/ImageEditor";
import PhotoGuideExamples from "../components/PhotoGuideExamples";
import SilhouetteOverlay from "../components/SilhouetteOverlay";
import { spacing, fontSize, fontWeight, borderRadius as br, colors } from "../theme/tokens";

type CaptureStep = "camera" | "preview" | "editing" | "validating" | "uploading" | "error";

export default function CaptureScreen() {
  const { mode } = useLocalSearchParams<{ mode?: string }>();
  const isBodyPhoto = mode !== "item";

  const navigation = useNavigation();
  const cameraRef = useRef<CameraView>(null);
  const [cameraPermission] = useCameraPermissions();
  const [galleryPermission, setGalleryPermission] = useState<boolean | null>(null);

  const [step, setStep] = useState<CaptureStep>("camera");
  const [capturedUri, setCapturedUri] = useState<string | null>(null);
  const [capturedWidth, setCapturedWidth] = useState(0);
  const [capturedHeight, setCapturedHeight] = useState(0);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  const handleEditorApply = useCallback((newUri: string, newWidth: number, newHeight: number) => {
    setCapturedUri(newUri);
    setCapturedWidth(newWidth);
    setCapturedHeight(newHeight);
    setStep("preview");
  }, []);

  useEffect(() => {
    navigation.setOptions({ title: "Take Your Photo", headerShown: true });
    ImagePicker.requestMediaLibraryPermissionsAsync().then((r) =>
      setGalleryPermission(r.granted),
    );
  }, [navigation]);

  const handleCapture = useCallback(async () => {
    if (!cameraRef.current) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 1 });
      if (!photo) return;
      setCapturedUri(photo.uri);
      setCapturedWidth(photo.width);
      setCapturedHeight(photo.height);
      setStep("preview");
    } catch {
      Alert.alert("Error", "Could not take photo. Please try again.");
    }
  }, []);

  const handlePickFromGallery = useCallback(async () => {
    const perm = galleryPermission ?? (await ImagePicker.requestMediaLibraryPermissionsAsync()).granted;
    if (!perm) {
      Alert.alert("Permission needed", "Gallery access is required.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 1,
    });

    if (result.canceled) return;

    const asset = result.assets[0];
    setCapturedUri(asset.uri);
    setCapturedWidth(asset.width ?? 0);
    setCapturedHeight(asset.height ?? 0);
    setStep("preview");
  }, [galleryPermission]);

  const handleUsePhoto = useCallback(async () => {
    if (!capturedUri) return;

    setStep("validating");
    setValidationErrors([]);

    const result = await validateImage(capturedUri, capturedWidth, capturedHeight, isBodyPhoto);

    if (!result.valid) {
      setValidationErrors(result.errors);
      setStep("error");
      return;
    }

    setStep("uploading");
    setUploadProgress(0);

    try {
      const manipulated = await ImageManipulator.manipulate(capturedUri)
        .resize({ width: MAX_LONG_EDGE_PX })
        .renderAsync();

      const compressed = await manipulated.saveAsync({
        compress: JPEG_QUALITY,
        format: SaveFormat.JPEG,
      });

      const { image_url } = await uploadApi.uploadImageWithProgress(
        compressed.uri,
        "photo.jpg",
        "image/jpeg",
        (progress) => setUploadProgress(progress),
      );

      if (isBodyPhoto) {
        await consentApi.setPhoto(DEMO_USER_ID, image_url);
        router.replace("/(tabs)");
      } else {
        router.replace(
          `/(tabs)/add-item?image_url=${encodeURIComponent(image_url)}`,
        );
      }
    } catch (e: any) {
      setErrorMsg(e.message || "Upload failed. Please try again.");
      setStep("error");
    }
  }, [capturedUri, capturedWidth, capturedHeight]);

  const handleRetake = useCallback(() => {
    setCapturedUri(null);
    setCapturedWidth(0);
    setCapturedHeight(0);
    setValidationErrors([]);
    setUploadProgress(0);
    setErrorMsg("");
    setStep("camera");
  }, []);

  // Render camera state
  if (step === "camera") {
    if (!cameraPermission) {
      return (
        <SafeAreaView style={{ flex: 1 }}>
          <View style={styles.centered}>
            <ActivityIndicator size="large" color="#333" />
          </View>
        </SafeAreaView>
      );
    }

    if (!cameraPermission.granted) {
      return (
        <SafeAreaView style={{ flex: 1 }}>
          <View style={styles.centered}>
            <Text style={styles.permissionText}>Camera access is required to take a photo.</Text>
            <TouchableOpacity
              style={styles.button}
              onPress={handlePickFromGallery}
            >
              <Text style={styles.buttonText}>Pick from Gallery instead</Text>
            </TouchableOpacity>
          </View>
        </SafeAreaView>
      );
    }

    return (
      <View style={styles.cameraContainer}>
        <View style={styles.cameraWrap}>
          <CameraView ref={cameraRef} style={styles.camera} facing={isBodyPhoto ? "front" : "back"} />
          {isBodyPhoto && <SilhouetteOverlay />}
        </View>

        {isBodyPhoto && <PhotoGuideExamples />}

        <View style={styles.cameraActions}>
          <TouchableOpacity style={styles.button} onPress={handleCapture}>
            <Text style={styles.buttonText}>Take Photo</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.button, styles.buttonSecondary]}
            onPress={handlePickFromGallery}
          >
            <Text style={styles.buttonTextSecondary}>Choose from Gallery</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // Render preview state
  if (step === "preview" && capturedUri) {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.container}>
          <Image source={{ uri: capturedUri }} style={styles.previewImage} />
          <View style={styles.previewInfo}>
            <Text style={styles.previewSize}>
              {capturedWidth} × {capturedHeight}
            </Text>
          </View>
          <View style={styles.previewActions}>
            <TouchableOpacity style={styles.button} onPress={handleUsePhoto}>
              <Text style={styles.buttonText}>Use This Photo</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.secondaryRow}
              onPress={() => setStep("editing")}
            >
              <Text style={styles.buttonTextSecondary}>Crop / Rotate</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.button, styles.buttonSecondary]}
              onPress={handleRetake}
            >
              <Text style={styles.buttonTextSecondary}>Retake</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // Render editing state
  if (step === "editing" && capturedUri) {
    return (
      <ImageEditor
        uri={capturedUri}
        imageWidth={capturedWidth || 1}
        imageHeight={capturedHeight || 1}
        onApply={handleEditorApply}
        onCancel={() => setStep("preview")}
      />
    );
  }

  // Render validating state
  if (step === "validating") {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.centered} accessibilityRole="progressbar" accessibilityLabel="Checking photo quality">
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Checking photo quality...</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Render uploading state
  if (step === "uploading") {
    return (
      <SafeAreaView style={{ flex: 1 }}>
        <View style={styles.centered} accessibilityRole="progressbar" accessibilityLabel={`Uploading photo: ${Math.round(uploadProgress * 100)}%`}>
          <ActivityIndicator size="large" color="#333" />
          <Text style={styles.loadingText}>Uploading photo...</Text>
          <View style={styles.progressBarBg}>
            <View
              style={[styles.progressBarFill, { width: `${uploadProgress * 100}%` }]}
            />
          </View>
          <Text style={styles.progressText}>{Math.round(uploadProgress * 100)}%</Text>
        </View>
      </SafeAreaView>
    );
  }

  // Render error state
  return (
    <SafeAreaView style={{ flex: 1 }}>
    <View style={styles.centered}>
      {capturedUri && (
        <Image source={{ uri: capturedUri }} style={styles.errorPreview} />
      )}
      <Text style={styles.errorTitle}>
        {validationErrors.length > 0 ? "Photo needs improvement" : "Upload failed"}
      </Text>

      {validationErrors.map((err, i) => (
        <Text key={i} style={styles.errorText}>
          {"\u2022"} {err}
        </Text>
      ))}
      {errorMsg ? <Text style={styles.errorText}>{errorMsg}</Text> : null}

      <TouchableOpacity style={styles.button} onPress={handleRetake}>
        <Text style={styles.buttonText}>Try Again</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.button, styles.buttonSecondary]}
        onPress={handlePickFromGallery}
      >
        <Text style={styles.buttonTextSecondary}>Choose from Gallery</Text>
      </TouchableOpacity>
    </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  cameraContainer: { flex: 1, backgroundColor: "#000" },
  cameraWrap: { flex: 1, position: "relative" },
  camera: { flex: 1 },
  cameraActions: {
    padding: spacing.xl,
    backgroundColor: colors.surface,
    gap: spacing.sm + 2,
  },
  button: {
    backgroundColor: colors.accent,
    borderRadius: br.md,
    padding: spacing.lg,
    alignItems: "center",
  },
  secondaryRow: {
    alignItems: "center",
    paddingVertical: spacing.sm + 2,
  },
  buttonSecondary: {
    backgroundColor: colors.surface,
    borderWidth: 1.5,
    borderColor: colors.accent,
  },
  buttonText: { color: colors.text.white, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  buttonTextSecondary: { color: colors.accent, fontSize: fontSize.base, fontWeight: fontWeight.bold },
  previewImage: {
    width: "100%",
    flex: 1,
    backgroundColor: "#000",
  },
  previewInfo: {
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  previewSize: { fontSize: fontSize.xs + 1, color: colors.text.tertiary },
  previewActions: {
    padding: spacing.xl,
    backgroundColor: colors.surface,
    gap: spacing.sm + 2,
  },
  loadingText: { fontSize: fontSize.base, color: "#666", marginTop: spacing.lg },
  progressBarBg: {
    width: "80%",
    height: spacing.xs + 2,
    backgroundColor: "#e0e0e0",
    borderRadius: spacing.xs - 1,
    marginTop: spacing.lg,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: colors.accent,
    borderRadius: spacing.xs - 1,
  },
  progressText: { fontSize: fontSize.sm, color: colors.text.tertiary, marginTop: spacing.sm },
  errorTitle: {
    fontSize: fontSize.lg,
    fontWeight: fontWeight.bold,
    color: colors.danger,
    marginBottom: spacing.md,
    marginTop: spacing.lg,
  },
  errorText: { fontSize: fontSize.sm, color: colors.danger, marginBottom: spacing.xs, lineHeight: 20 },
  errorPreview: { width: 160, height: 200, borderRadius: br.md },
  permissionText: { fontSize: fontSize.base, color: "#666", textAlign: "center", marginBottom: spacing.xl },
});
