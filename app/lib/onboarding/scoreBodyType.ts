export const VALID_BODY_TYPES = [
  "rectangle",
  "hourglass",
  "pear",
  "apple",
  "inverted_triangle",
] as const;

export type BodyType = (typeof VALID_BODY_TYPES)[number];

export interface OnboardingAnswers {
  shoulderHipBalance: "shoulders_wider" | "hips_wider" | "about_equal";
  waistDefinition: "very_defined" | "little_none";
  weightCarry: "midsection" | "hips_thighs" | "evenly";
  silhouette: BodyType;
}

type ScoreMap = Record<BodyType, number>;

const zeroScores = (): ScoreMap => ({
  rectangle: 0,
  hourglass: 0,
  pear: 0,
  apple: 0,
  inverted_triangle: 0,
});

export function scoreBodyType(answers: OnboardingAnswers): BodyType {
  const scores = zeroScores();
  const add = (type: BodyType, n: number) => {
    scores[type] += n;
  };

  switch (answers.shoulderHipBalance) {
    case "shoulders_wider":
      add("inverted_triangle", 3);
      break;
    case "hips_wider":
      add("pear", 3);
      break;
    case "about_equal":
      add("rectangle", 2);
      add("hourglass", 1);
      break;
  }

  switch (answers.waistDefinition) {
    case "very_defined":
      add("hourglass", 3);
      break;
    case "little_none":
      add("apple", 2);
      add("rectangle", 1);
      break;
  }

  switch (answers.weightCarry) {
    case "midsection":
      add("apple", 3);
      break;
    case "hips_thighs":
      add("pear", 3);
      break;
    case "evenly":
      add("rectangle", 2);
      add("inverted_triangle", 1);
      break;
  }

  if (answers.silhouette) {
    add(answers.silhouette, 5);
  }

  let best: BodyType = "rectangle";
  let bestScore = -Infinity;
  for (const type of VALID_BODY_TYPES) {
    if (scores[type] > bestScore) {
      bestScore = scores[type];
      best = type;
    }
  }
  return best;
}
