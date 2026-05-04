import { useEffect, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import { Button, Container, Group, Skeleton, Text, Title } from "@mantine/core";
import ReactMarkdown from "react-markdown";
import { getCurrentUser } from "../../auth";
import { WorldPageState, loadWorld } from "./worldPageState";

interface WorldPageProps {
  worldId: string;
}

export const WorldPage = observer(function WorldPage({ worldId }: WorldPageProps) {
  const [state] = useState(() => new WorldPageState(worldId));
  const navigate = useNavigate();
  const user = getCurrentUser();
  const canEdit = user?.role === "editor" || user?.role === "admin";

  useEffect(() => {
    const ctrl = new AbortController();
    loadWorld(state, ctrl.signal);
    return () => ctrl.abort();
  }, []);

  if (state.worldStatus === "error") {
    return (
      <Container size="sm" py="xl">
        <Text c="red">{state.worldError}</Text>
      </Container>
    );
  }

  if (state.world === null) {
    return (
      <Container size="sm" py="xl">
        <Skeleton height={32} mb="md" />
        <Skeleton height={16} mb="xs" />
        <Skeleton height={16} mb="xs" />
        <Skeleton height={16} width="60%" />
      </Container>
    );
  }

  const world = state.world;
  return (
    <Container size="sm" py="xl">
      <Title order={2} mb="sm">{world.name}</Title>
      <div className="md-body" style={{ color: "var(--mantine-color-dimmed)", marginBottom: "var(--mantine-spacing-xl)", fontSize: "var(--mantine-font-size-sm)" }}>
        <ReactMarkdown>{world.description || "No description."}</ReactMarkdown>
      </div>
      <Group>
        <Button onClick={() => navigate(`/worlds/${world.id}/new`)}>
          Start New Chat
        </Button>
        {canEdit && (
          <Button variant="light" color="yellow" component="a" href={`/admin/worlds/${world.id}`}>
            Edit World
          </Button>
        )}
      </Group>
    </Container>
  );
});
