import { useEffect, useState } from "react";
import { Button, Container, Group, Skeleton, Text, Title } from "@mantine/core";
import { listPublicWorlds } from "../../api/chat";
import { getCurrentUser } from "../../auth";

function _worldIdFromPath(): string {
  const match = window.location.pathname.match(/\/worlds\/(\d+)$/);
  return match?.[1] ?? "";
}

export function WorldPage() {
  const worldId = _worldIdFromPath();
  const [world, setWorld] = useState<WorldInfo | null>(null);
  const user = getCurrentUser();
  const canEdit = user?.role === "editor" || user?.role === "admin";

  useEffect(() => {
    listPublicWorlds().then((worlds) => {
      setWorld(worlds.find((w) => w.id === worldId) ?? null);
    }).catch(() => {});
  }, [worldId]);

  if (!world) {
    return (
      <Container size="sm" py="xl">
        <Skeleton height={32} mb="md" />
        <Skeleton height={16} mb="xs" />
        <Skeleton height={16} mb="xs" />
        <Skeleton height={16} width="60%" />
      </Container>
    );
  }

  return (
    <Container size="sm" py="xl">
      <Title order={2} mb="sm">{world.name}</Title>
      <Text size="sm" c="dimmed" style={{ whiteSpace: "pre-wrap" }} mb="xl">
        {world.description || "No description."}
      </Text>
      <Group>
        <Button component="a" href={`/worlds/${world.id}/new`}>
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
}
