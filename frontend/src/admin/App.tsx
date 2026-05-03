import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import { IconDatabase, IconRoute, IconServer, IconUsers, IconWorld } from "@tabler/icons-react";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { loadTranslationSettings } from "../utils/translationSettings";
import { AppLayout } from "../components/AppLayout";
import type { NavItem } from "../components/AppSidebar";
import { AdminRoutes } from "./routes";

const NAV_ITEMS: NavItem[] = [
  { icon: IconUsers, label: "Users", href: "/admin/" },
  { icon: IconWorld, label: "Worlds", href: "/admin/worlds" },
  { icon: IconRoute, label: "Pipelines", href: "/admin/pipelines" },
  { icon: IconServer, label: "LLM Servers", href: "/admin/llm-servers" },
  { icon: IconDatabase, label: "Database", href: "/admin/database" },
];

export function App() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      window.location.href = "/login/";
      return;
    }
    loadTranslationSettings();
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <BrowserRouter basename="/admin">
        <AppLayout navItems={NAV_ITEMS} logoHref="/">
          <AdminRoutes />
        </AppLayout>
      </BrowserRouter>
    </MantineProvider>
  );
}
