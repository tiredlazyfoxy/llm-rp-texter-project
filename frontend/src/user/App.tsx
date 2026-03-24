import { useEffect, useState } from "react";
import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { loadTranslationSettings } from "../utils/translationSettings";
import { AppLayout } from "../components/AppLayout";
import { UserSidebar } from "./components/UserSidebar";
import { ChatListPage } from "./pages/ChatListPage";
import { CharacterSetupPage } from "./pages/CharacterSetupPage";
import { ChatViewPage } from "./pages/ChatViewPage";
import { WorldPage } from "./pages/WorldPage";

function UserContent() {
  const path = window.location.pathname;
  if (/\/chat\/\d+/.test(path)) return <ChatViewPage />;
  if (/\/worlds\/\d+\/new/.test(path)) return <CharacterSetupPage />;
  if (/\/worlds\/\d+$/.test(path)) return <WorldPage />;
  return <ChatListPage />;
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
      <AppLayout sidebar={<UserSidebar />}>
        <UserContent />
      </AppLayout>
    </MantineProvider>
  );
}
