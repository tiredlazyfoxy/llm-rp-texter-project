import { useEffect, useState } from "react";
import { MantineProvider, Container, Text } from "@mantine/core";
import "@mantine/core/styles.css";
import "../global.css";
import { theme } from "../theme";
import { AppLayout } from "../components/AppLayout";

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
      <AppLayout>
        <Container size="lg" py="md">
          <Text c="dimmed">Admin SPA placeholder</Text>
        </Container>
      </AppLayout>
    </MantineProvider>
  );
}
