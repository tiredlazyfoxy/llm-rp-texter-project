import { useEffect, useState } from "react";
import { MantineProvider, Container, Text } from "@mantine/core";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { AppHeader } from "../components/AppHeader";

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
      <AppHeader />
      <Container size="lg" py="md">
        <Text c="dimmed">User SPA placeholder</Text>
      </Container>
    </MantineProvider>
  );
}
