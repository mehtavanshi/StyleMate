import { Tabs } from "expo-router";
import { Calendar, Camera, House, PlusCircle, Shirt, Sparkles } from "../../lib/icons";

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: true,
        tabBarActiveTintColor: "#333",
        tabBarInactiveTintColor: "#999",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <House color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="wardrobe"
        options={{
          title: "Wardrobe",
          tabBarIcon: ({ color, size }) => <Shirt color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="add-item"
        options={{
          title: "Add Item",
          tabBarIcon: ({ color, size }) => <PlusCircle color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="outfit-suggestions"
        options={{
          title: "Outfits",
          tabBarIcon: ({ color, size }) => <Sparkles color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="my-tryons"
        options={{
          title: "My Try-Ons",
          tabBarIcon: ({ color, size }) => <Camera color={color} size={size} strokeWidth={1.5} />,
        }}
      />
      <Tabs.Screen
        name="calendar"
        options={{
          title: "Calendar",
          tabBarIcon: ({ color, size }) => <Calendar color={color} size={size} strokeWidth={1.5} />,
        }}
      />
    </Tabs>
  );
}
