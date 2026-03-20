import { useEffect, useState } from "react";
import {
  Group,
  Image,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import {
  IconChevronDown,
  IconChevronRight,
  IconLayoutSidebarLeftCollapse,
  IconMessage,
  IconWorld,
} from "@tabler/icons-react";
import { listMyChats, listPublicWorlds } from "../../api/chat";
import { formatDate } from "../../utils/formatDate";

interface WorldEntry {
  world: WorldInfo;
  chats: ChatSessionItem[];
  lastModified: string;
}

export function UserSidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [worlds, setWorlds] = useState<WorldInfo[]>([]);
  const [chats, setChats] = useState<ChatSessionItem[]>([]);
  const [expandedWorlds, setExpandedWorlds] = useState<Set<string>>(new Set());
  const [showMoreWorlds, setShowMoreWorlds] = useState<Set<string>>(new Set());

  useEffect(() => {
    listPublicWorlds().then(setWorlds).catch(() => {});
    listMyChats().then(setChats).catch(() => {});
  }, []);

  const width = collapsed ? 48 : 240;

  // Build world entries: worlds with chats first (by last chat), then worlds without chats
  const chatsByWorld = new Map<string, ChatSessionItem[]>();
  for (const chat of chats) {
    const arr = chatsByWorld.get(chat.world_id) ?? [];
    arr.push(chat);
    chatsByWorld.set(chat.world_id, arr);
  }

  const withChats: WorldEntry[] = [];
  const withoutChats: WorldEntry[] = [];
  for (const world of worlds) {
    const worldChats = (chatsByWorld.get(world.id) ?? []).sort(
      (a, b) => b.modified_at.localeCompare(a.modified_at),
    );
    const entry: WorldEntry = {
      world,
      chats: worldChats,
      lastModified: worldChats[0]?.modified_at ?? "",
    };
    if (worldChats.length > 0) withChats.push(entry);
    else withoutChats.push(entry);
  }
  withChats.sort((a, b) => b.lastModified.localeCompare(a.lastModified));
  withoutChats.sort((a, b) => a.world.name.localeCompare(b.world.name));
  const entries = [...withChats, ...withoutChats];

  function toggleWorld(worldId: string) {
    setExpandedWorlds((prev) => {
      const next = new Set(prev);
      if (next.has(worldId)) next.delete(worldId);
      else next.add(worldId);
      return next;
    });
  }

  const path = window.location.pathname;

  return (
    <nav
        style={{
          width,
          minWidth: width,
          height: "100%",
          borderRight: "1px solid var(--mantine-color-dark-4)",
          display: "flex",
          flexDirection: "column",
          transition: "width 150ms ease",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        {/* Logo */}
        <Group h={48} px="xs" justify={collapsed ? "center" : "space-between"}>
          {collapsed ? (
            <UnstyledButton onClick={() => setCollapsed(false)} style={{ display: "flex", alignItems: "center" }}>
              <Image src="/favicon.svg" w={24} h={24} />
            </UnstyledButton>
          ) : (
            <>
              <Group gap="xs" style={{ cursor: "default" }}>
                <Image src="/logo.svg" w={24} h={24} />
                <Text fw={600} size="md" c="dimmed">LLMRP</Text>
              </Group>
              <UnstyledButton onClick={() => setCollapsed(true)} p={4} style={{ display: "flex" }}>
                <IconLayoutSidebarLeftCollapse size={20} color="var(--mantine-color-dimmed)" />
              </UnstyledButton>
            </>
          )}
        </Group>

        {/* World list */}
        <Stack gap={0} px={collapsed ? 4 : 4} py="xs" style={{ flex: 1, overflowY: "auto" }}>
          {entries.map(({ world, chats: wChats }) => {
            const isExpanded = expandedWorlds.has(world.id);
            const showAll = showMoreWorlds.has(world.id);
            const visibleChats = showAll ? wChats : wChats.slice(0, 10);
            const remaining = wChats.length - 10;

            const worldRow = (
              <UnstyledButton
                key={`world-${world.id}`}
                p={8}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  borderRadius: "var(--mantine-radius-sm)",
                }}
                onClick={() => {
                  if (collapsed) return;
                  toggleWorld(world.id);
                }}
                onAuxClick={() => setSelectedWorld(world)}
              >
                {!collapsed && (
                  isExpanded
                    ? <IconChevronDown size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
                    : <IconChevronRight size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
                )}
                <IconWorld size={18} color="var(--mantine-color-steel-5)" style={{ flexShrink: 0 }} />
                {!collapsed && (
                  <Text
                    size="sm"
                    c="dimmed"
                    style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}
                    title={world.name}
                  >
                    {world.name}
                  </Text>
                )}
              </UnstyledButton>
            );

            return (
              <div key={world.id}>
                {collapsed ? (
                  <Tooltip label={world.name} position="right" withArrow>
                    <UnstyledButton
                      p={8}
                      style={{ width: "100%", display: "flex", justifyContent: "center" }}
                      component="a"
                      href={`/worlds/${world.id}`}
                    >
                      <IconWorld size={18} color="var(--mantine-color-steel-5)" />
                    </UnstyledButton>
                  </Tooltip>
                ) : (
                  <UnstyledButton
                    p={8}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      borderRadius: "var(--mantine-radius-sm)",
                    }}
                    onClick={() => toggleWorld(world.id)}
                  >
                    {isExpanded
                      ? <IconChevronDown size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
                      : <IconChevronRight size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
                    }
                    <IconWorld size={18} color="var(--mantine-color-steel-5)" style={{ flexShrink: 0 }} />
                    <Text
                      size="sm"
                      fw={500}
                      c="dimmed"
                      style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}
                      title={world.name}
                      component="a"
                      href={`/worlds/${world.id}`}
                      onClick={(e) => e.stopPropagation()}
                    >
                      {world.name}
                    </Text>
                  </UnstyledButton>
                )}

                {!collapsed && isExpanded && (
                  <Stack gap={0} pl={28}>
                    {visibleChats.map((chat) => {
                      const active = path === `/chat/${chat.id}`;
                      return (
                        <UnstyledButton
                          key={chat.id}
                          component="a"
                          href={`/chat/${chat.id}`}
                          p={6}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            borderRadius: "var(--mantine-radius-sm)",
                            backgroundColor: active ? "var(--mantine-color-dark-5)" : undefined,
                          }}
                        >
                          <IconMessage
                            size={14}
                            color={active ? "var(--mantine-color-steel-5)" : "var(--mantine-color-dimmed)"}
                            style={{ flexShrink: 0 }}
                          />
                          <Stack gap={0} style={{ overflow: "hidden", flex: 1 }}>
                            <Text
                              size="xs"
                              c={active ? "steel.5" : "dimmed"}
                              style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}
                            >
                              {chat.character_name}
                            </Text>
                            <Text size="xs" c="dimmed" opacity={0.6}>
                              T{chat.current_turn} · {formatDate(chat.modified_at)}
                            </Text>
                          </Stack>
                        </UnstyledButton>
                      );
                    })}
                    {!showAll && remaining > 0 && (
                      <UnstyledButton
                        p={6}
                        onClick={() => setShowMoreWorlds((prev) => new Set([...prev, world.id]))}
                      >
                        <Text size="xs" c="dimmed" opacity={0.7}>… {remaining} more</Text>
                      </UnstyledButton>
                    )}
                    {wChats.length === 0 && (
                      <Text size="xs" c="dimmed" px={6} py={4} opacity={0.6}>No chats yet</Text>
                    )}
                  </Stack>
                )}
              </div>
            );
          })}
        </Stack>
      </nav>
  );
}
