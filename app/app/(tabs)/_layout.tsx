import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs screenOptions={{ headerShown: true }}>
      <Tabs.Screen name="index" options={{ title: "Home" }} />
      <Tabs.Screen name="wardrobe" options={{ title: "Wardrobe" }} />
      <Tabs.Screen name="add-item" options={{ title: "Add Item" }} />
      <Tabs.Screen
        name="outfit-suggestions"
        options={{ title: "Outfits" }}
      />
      <Tabs.Screen
        name="my-tryons"
        options={{ title: "My Try-Ons" }}
      />
      <Tabs.Screen name="calendar" options={{ title: "Calendar" }} />
    </Tabs>
  );
}
