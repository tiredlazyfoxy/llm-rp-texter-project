import { useEffect, useState } from "react";
import { MantineProvider } from "@mantine/core";
import { IconServer, IconUsers, IconWorld } from "@tabler/icons-react";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { AppLayout } from "../components/AppLayout";
import type { NavItem } from "../components/AppSidebar";
import { LlmServersPage } from "./pages/LlmServersPage";
import { UsersPage } from "./pages/UsersPage";

const NAV_ITEMS: NavItem[] = [
  { icon: IconUsers, label: "Users", href: "/admin/" },
  { icon: IconWorld, label: "Worlds", href: "/admin/worlds" },
  { icon: IconServer, label: "LLM Servers", href: "/admin/llm-servers" },
];

function AdminContent() {
  const path = window.location.pathname;
  if (path.startsWith("/admin/llm-servers")) {
    return <LlmServersPage />;
  }
  if (path.startsWith("/admin/worlds")) {
    return <div style={{ padding: 16, color: "var(--mantine-color-dimmed)" }}>Worlds — coming soon</div>;
  }
  return <UsersPage />;
}

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
        <AdminContent />
      </AppLayout>
    </MantineProvider>
  );
}
