import { useEffect, useState } from "react";
import { MantineProvider, Container, Text } from "@mantine/core";
import { IconMessages, IconWorld } from "@tabler/icons-react";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { AppLayout } from "../components/AppLayout";
import type { NavItem } from "../components/AppSidebar";

const NAV_ITEMS: NavItem[] = [
  { icon: IconMessages, label: "Chats", href: "/" },
  { icon: IconWorld, label: "Worlds", href: "/worlds" },
];

export function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      window.location.href = "/login/";
      return;
    }
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <AppLayout navItems={NAV_ITEMS}>
        <Container size="lg" py="md">
          <Text c="dimmed">User SPA placeholder</Text>
        </Container>
      </AppLayout>
    </MantineProvider>
  );
}
