import { useEffect } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { useNavigation } from "expo-router";

export default function PrivacyScreen() {
  const navigation = useNavigation();

  useEffect(() => {
    navigation.setOptions({ title: "Privacy Policy", headerShown: true });
  }, [navigation]);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Text style={styles.heading}>Privacy Policy</Text>
      <Text style={styles.lastUpdated}>Last updated: July 2026</Text>

      <Section title="What information we collect">
        <Text style={styles.body}>
          When you use StyleMate's virtual try-on feature, you may upload a
          full-body photo. This photo is stored on our secure server and is
          associated only with your account.
        </Text>
      </Section>

      <Section title="Why we collect it">
        <Text style={styles.body}>
          Your photo is used exclusively for rendering clothing items on your
          body so you can preview how they look before wearing them.
        </Text>
      </Section>

      <Section title="What we do NOT do with your photo">
        <Text style={styles.body}>
          We do NOT use your photo to train AI or machine learning models. We
          do NOT share your photo with other users. We do NOT sell or transfer
          your photo to any third party. Your photo is used only for your
          personal virtual try-on experience.
        </Text>
      </Section>

      <Section title="How long we keep it">
        <Text style={styles.body}>
          Your photo is stored until you choose to delete it, or until your
          account has been inactive for 90 days — whichever comes first. You
          can delete your photo at any time from the app's Settings or Home
          screen. When you delete your photo, it is permanently removed from
          our server.
        </Text>
      </Section>

      <Section title="Data security">
        <Text style={styles.body}>
          We use industry-standard security measures to protect your data.
          All photo uploads are handled over encrypted connections, and
          stored files are not publicly accessible.
        </Text>
      </Section>

      <Section title="Your rights">
        <Text style={styles.body}>
          You have the right to withdraw your consent at any time. You have
          the right to request deletion of your photo. You have the right to
          request a copy of any data we hold about you. To exercise any of
          these rights, use the in-app controls or contact us.
        </Text>
      </Section>

      <Section title="Contact">
        <Text style={styles.body}>
          If you have questions about this policy or your data, please contact
          us at privacy@stylemate.app.
        </Text>
      </Section>
    </ScrollView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 20, paddingBottom: 40 },
  heading: { fontSize: 24, fontWeight: "800", marginBottom: 4 },
  lastUpdated: { fontSize: 13, color: "#999", marginBottom: 24 },
  section: { marginBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 8, color: "#333" },
  body: { fontSize: 15, color: "#555", lineHeight: 22 },
});
