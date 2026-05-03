import { useEffect, useState } from "react";
import { BrowserRouter } from "react-router-dom";
import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { loadTranslationSettings } from "../utils/translationSettings";
import { AppLayout } from "../components/AppLayout";
import { UserSidebar } from "./components/UserSidebar";
import { UserRoutes } from "./routes";

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
      <BrowserRouter>
        <AppLayout sidebar={<UserSidebar />}>
          <UserRoutes />
        </AppLayout>
      </BrowserRouter>
    </MantineProvider>
  );
}
