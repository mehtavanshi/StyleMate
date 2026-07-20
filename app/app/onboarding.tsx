import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { useForm } from "react-hook-form";
import { router, useNavigation } from "expo-router";

import { usersApi } from "../lib/api";
import {
  BODY_TYPE_ICONS,
  AppleIcon,
  HourglassIcon,
  InvertedTriangleIcon,
  PearIcon,
  RectangleIcon,
} from "../lib/onboarding/bodyShapeIcons";
import {
  BodyType,
  OnboardingAnswers,
  VALID_BODY_TYPES,
  scoreBodyType,
} from "../lib/onboarding/scoreBodyType";

const ONBOARDING_FLAG = "onboarding_complete";
const DEMO_USER_ID = 1;

interface Option<T extends string> {
  value: T;
  label: string;
  Icon: (props: { size?: number; color?: string }) => React.ReactElement;
}

const QUESTIONS: {
  name: keyof OnboardingAnswers;
  title: string;
  options: Option<string>[];
}[] = [
  {
    name: "shoulderHipBalance",
    title: "Which is closest to your shoulder / hip balance?",
    options: [
      { value: "shoulders_wider", label: "Shoulders wider than hips", Icon: InvertedTriangleIcon },
      { value: "hips_wider", label: "Hips wider than shoulders", Icon: PearIcon },
      { value: "about_equal", label: "About equal", Icon: RectangleIcon },
    ],
  },
  {
    name: "waistDefinition",
    title: "How defined is your waist?",
    options: [
      { value: "very_defined", label: "Very defined (waist noticeably narrower)", Icon: HourglassIcon },
      { value: "little_none", label: "Little or no definition", Icon: AppleIcon },
    ],
  },
  {
    name: "weightCarry",
    title: "Where do you carry most of your weight?",
    options: [
      { value: "midsection", label: "Midsection", Icon: AppleIcon },
      { value: "hips_thighs", label: "Hips / thighs", Icon: PearIcon },
      { value: "evenly", label: "Evenly", Icon: RectangleIcon },
    ],
  },
  {
    name: "silhouette",
    title: "Which silhouette matches you best?",
    options: VALID_BODY_TYPES.map((bt) => ({
      value: bt,
      label: bt.replace("_", " "),
      Icon: BODY_TYPE_ICONS[bt],
    })),
  },
];

export default function OnboardingScreen() {
  const navigation = useNavigation();
  const { watch, setValue, handleSubmit } = useForm<OnboardingAnswers>({
    mode: "onChange",
    defaultValues: {
      shoulderHipBalance: undefined as any,
      waistDefinition: undefined as any,
      weightCarry: undefined as any,
      silhouette: undefined as any,
    },
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    navigation.setOptions({ title: "About your shape", headerShown: true });
  }, [navigation]);

  const answers = watch();

  const allAnswered =
    answers.shoulderHipBalance &&
    answers.waistDefinition &&
    answers.weightCarry &&
    answers.silhouette;

  const onSubmit = async (data: OnboardingAnswers) => {
    setSubmitting(true);
    setError(null);
    try {
      const bodyType = scoreBodyType(data);
      await usersApi.setBodyType(DEMO_USER_ID, bodyType);
      await AsyncStorage.setItem(ONBOARDING_FLAG, "1");
      router.replace("/(tabs)");
    } catch (e: any) {
      setError(e.message || "Something went wrong. Please try again.");
      Alert.alert("Error", e.message || "Could not save your shape.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>About your shape</Text>
      <Text style={styles.subtitle}>
        Answer a few quick questions so we can tailor outfit suggestions to your
        body type.
      </Text>

      {QUESTIONS.map((q, qi) => (
        <View key={q.name} style={styles.question}>
          <Text style={styles.questionTitle}>
            {qi + 1}. {q.title}
          </Text>
          <View style={styles.options}>
            {q.options.map((opt) => {
              const selected = (answers[q.name] as string) === opt.value;
              const OptionIcon = opt.Icon;
              return (
                <TouchableOpacity
                  key={String(opt.value)}
                  style={[styles.card, selected && styles.cardSelected]}
                  onPress={() =>
                    setValue(q.name, opt.value as any, { shouldValidate: true })
                  }
                  activeOpacity={0.8}
                >
                  <View style={styles.iconWrap}>
                    <OptionIcon size={56} color={selected ? "#fff" : "#333"} />
                  </View>
                  <Text style={[styles.cardLabel, selected && styles.cardLabelSelected]}>
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        </View>
      ))}

      {error && <Text style={styles.errorText}>{error}</Text>}

      <TouchableOpacity
        style={[styles.submitButton, (!allAnswered || submitting) && styles.submitDisabled]}
        onPress={handleSubmit(onSubmit)}
        disabled={!allAnswered || submitting}
      >
        {submitting ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitText}>Continue</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 20, paddingBottom: 40 },
  heading: { fontSize: 24, fontWeight: "800", marginBottom: 6 },
  subtitle: { fontSize: 15, color: "#666", marginBottom: 20, lineHeight: 22 },
  question: { marginBottom: 22 },
  questionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12, color: "#333" },
  options: { gap: 10 },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    elevation: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    borderWidth: 2,
    borderColor: "transparent",
  },
  cardSelected: { borderColor: "#333", backgroundColor: "#333" },
  iconWrap: {
    width: 64,
    height: 64,
    borderRadius: 10,
    backgroundColor: "#f0f0f0",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 14,
  },
  cardLabel: { fontSize: 15, fontWeight: "600", color: "#333", flexShrink: 1 },
  cardLabelSelected: { color: "#fff" },
  errorText: { color: "#c00", fontSize: 14, marginBottom: 12 },
  submitButton: {
    backgroundColor: "#333",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  submitDisabled: { backgroundColor: "#aaa" },
  submitText: { color: "#fff", fontSize: 16, fontWeight: "700" },
});
