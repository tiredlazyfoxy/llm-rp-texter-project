import { Button, Group, Modal, ScrollArea, Text, Title } from "@mantine/core";
import { getCurrentUser } from "../../auth";

interface WorldInfoModalProps {
  world: WorldInfo | null;
  onClose: () => void;
}

export function WorldInfoModal({ world, onClose }: WorldInfoModalProps) {
  const user = getCurrentUser();
  const canEdit = user?.role === "editor" || user?.role === "admin";

  return (
    <Modal
      opened={world !== null}
      onClose={onClose}
      title={<Title order={4}>{world?.name}</Title>}
      size="md"
    >
      {world && (
        <>
          <ScrollArea mah={300} mb="md">
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {world.description || "No description."}
            </Text>
          </ScrollArea>
          <Group justify="flex-end" gap="sm">
            {canEdit && (
              <Button
                variant="light"
                color="yellow"
                component="a"
                href={`/admin/worlds/${world.id}`}
              >
                Edit World
              </Button>
            )}
            <Button
              component="a"
              href={`/worlds/${world.id}/new`}
            >
              Start New Chat
            </Button>
          </Group>
        </>
      )}
    </Modal>
  );
}
