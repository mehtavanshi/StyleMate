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
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { router, useLocalSearchParams, useNavigation } from "expo-router";

import { consentApi, DEMO_USER_ID, uploadApi } from "../lib/api";
import { MAX_LONG_EDGE_PX, JPEG_QUALITY } from "../lib/constants";
import { validateImage } from "../lib/imageValidation";
import PhotoGuideExamples from "../components/PhotoGuideExamples";
import SilhouetteOverlay from "../components/SilhouetteOverlay";

type CaptureStep = "camera" | "preview" | "validating" | "uploading" | "error";

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
        <View style={styles.centered}>
          <ActivityIndicator size="large" color="#333" />
        </View>
      );
    }

    if (!cameraPermission.granted) {
      return (
        <View style={styles.centered}>
          <Text style={styles.permissionText}>Camera access is required to take a photo.</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={handlePickFromGallery}
          >
            <Text style={styles.buttonText}>Pick from Gallery instead</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return (
      <View style={styles.cameraContainer}>
        <View style={styles.cameraWrap}>
          <CameraView ref={cameraRef} style={styles.camera} facing="back" />
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
            style={[styles.button, styles.buttonSecondary]}
            onPress={handleRetake}
          >
            <Text style={styles.buttonTextSecondary}>Retake</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  // Render validating state
  if (step === "validating") {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Checking photo quality...</Text>
      </View>
    );
  }

  // Render uploading state
  if (step === "uploading") {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color="#333" />
        <Text style={styles.loadingText}>Uploading photo...</Text>
        <View style={styles.progressBarBg}>
          <View
            style={[styles.progressBarFill, { width: `${uploadProgress * 100}%` }]}
          />
        </View>
        <Text style={styles.progressText}>{Math.round(uploadProgress * 100)}%</Text>
      </View>
    );
  }

  // Render error state
  return (
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
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  centered: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#f5f5f5",
    padding: 20,
  },
  cameraContainer: { flex: 1, backgroundColor: "#000" },
  cameraWrap: { flex: 1, position: "relative" },
  camera: { flex: 1 },
  cameraActions: {
    padding: 20,
    backgroundColor: "#fff",
    gap: 10,
  },
  button: {
    backgroundColor: "#333",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
  },
  buttonSecondary: {
    backgroundColor: "#fff",
    borderWidth: 1.5,
    borderColor: "#333",
  },
  buttonText: { color: "#fff", fontSize: 16, fontWeight: "700" },
  buttonTextSecondary: { color: "#333", fontSize: 16, fontWeight: "700" },
  previewImage: {
    width: "100%",
    flex: 1,
    backgroundColor: "#000",
  },
  previewInfo: {
    backgroundColor: "#fff",
    paddingHorizontal: 20,
    paddingVertical: 8,
    alignItems: "center",
  },
  previewSize: { fontSize: 13, color: "#888" },
  previewActions: {
    padding: 20,
    backgroundColor: "#fff",
    gap: 10,
  },
  loadingText: { fontSize: 16, color: "#666", marginTop: 16 },
  progressBarBg: {
    width: "80%",
    height: 6,
    backgroundColor: "#e0e0e0",
    borderRadius: 3,
    marginTop: 16,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: "#333",
    borderRadius: 3,
  },
  progressText: { fontSize: 14, color: "#888", marginTop: 8 },
  errorTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#c00",
    marginBottom: 12,
    marginTop: 16,
  },
  errorText: { fontSize: 14, color: "#c00", marginBottom: 4, lineHeight: 20 },
  errorPreview: { width: 160, height: 200, borderRadius: 10 },
  permissionText: { fontSize: 16, color: "#666", textAlign: "center", marginBottom: 20 },
});
