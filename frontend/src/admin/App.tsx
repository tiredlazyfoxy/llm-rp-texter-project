import { useEffect, useState } from "react";
import { MantineProvider } from "@mantine/core";
import { IconDatabase, IconServer, IconUsers, IconWorld } from "@tabler/icons-react";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { loadTranslationSettings } from "../utils/translationSettings";
import { AppLayout } from "../components/AppLayout";
import type { NavItem } from "../components/AppSidebar";
import { DbManagementPage } from "./pages/DbManagementPage";
import { DocumentEditPage } from "./pages/DocumentEditPage";
import { WorldFieldEditPage } from "./pages/WorldFieldEditPage";
import { LlmServersPage } from "./pages/LlmServersPage";
import { UsersPage } from "./pages/UsersPage";
import { WorldEditPage } from "./pages/WorldEditPage";
import { WorldsListPage } from "./pages/WorldsListPage";
import { PipelineStageEditPage } from "./pages/PipelineStageEditPage";
import { WorldViewPage } from "./pages/WorldViewPage";

const NAV_ITEMS: NavItem[] = [
  { icon: IconUsers, label: "Users", href: "/admin/" },
  { icon: IconWorld, label: "Worlds", href: "/admin/worlds" },
  { icon: IconServer, label: "LLM Servers", href: "/admin/llm-servers" },
  { icon: IconDatabase, label: "Database", href: "/admin/database" },
];

function AdminContent() {
  const path = window.location.pathname;
  if (path.startsWith("/admin/llm-servers")) {
    return <LlmServersPage />;
  }
  if (path.startsWith("/admin/database")) {
    return <DbManagementPage />;
  }
  if (path.startsWith("/admin/worlds")) {
    if (/\/admin\/worlds\/\d+\/documents\/\d+\/edit/.test(path)) return <DocumentEditPage />;
    if (/\/admin\/worlds\/\d+\/pipeline\/\d+/.test(path)) return <PipelineStageEditPage />;
    if (/\/admin\/worlds\/\d+\/field\/\w+/.test(path)) return <WorldFieldEditPage />;
    if (/\/admin\/worlds\/\d+\/edit/.test(path)) return <WorldEditPage />;
    if (/\/admin\/worlds\/\d+/.test(path)) return <WorldViewPage />;
    return <WorldsListPage />;
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
    loadTranslationSettings();
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <MantineProvider theme={theme} defaultColorScheme="dark">
      <AppLayout navItems={NAV_ITEMS} logoHref="/">
        <AdminContent />
      </AppLayout>
    </MantineProvider>
  );
}
