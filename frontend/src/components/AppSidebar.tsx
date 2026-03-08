import { Group, Image, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import {
  IconLayoutSidebarLeftCollapse,
  IconMessages,
  IconWorld,
  type Icon,
} from "@tabler/icons-react";

interface NavItem {
  icon: Icon;
  label: string;
  href: string;
}

const NAV_ITEMS: NavItem[] = [
  { icon: IconMessages, label: "Chats", href: "/" },
  { icon: IconWorld, label: "Worlds", href: "/worlds" },
];

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function AppSidebar({ collapsed, onToggle }: AppSidebarProps) {
  const width = collapsed ? 48 : 220;

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
      {/* Top: logo / site icon — click expands when collapsed */}
      <Group h={48} px="xs" justify={collapsed ? "center" : "space-between"}>
        {collapsed ? (
          <UnstyledButton onClick={onToggle} style={{ display: "flex", alignItems: "center" }}>
            <Image src="/favicon.svg" w={24} h={24} />
          </UnstyledButton>
        ) : (
          <>
            <Group gap="xs" style={{ cursor: "default" }}>
              <Image src="/logo.svg" w={24} h={24} />
              <Text fw={600} size="md" c="dimmed">
                LLMRP
              </Text>
            </Group>
            <UnstyledButton onClick={onToggle} p={4} style={{ display: "flex" }}>
              <IconLayoutSidebarLeftCollapse size={20} color="var(--mantine-color-dimmed)" />
            </UnstyledButton>
          </>
        )}
      </Group>

      {/* Nav items */}
      <Stack gap={2} px={4} py="xs" style={{ flex: 1 }}>
        {NAV_ITEMS.map((item) => (
          <SidebarLink key={item.href} item={item} collapsed={collapsed} />
        ))}
      </Stack>
    </nav>
  );
}

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const active = window.location.pathname === item.href ||
    (item.href !== "/" && window.location.pathname.startsWith(item.href));

  const content = (
    <UnstyledButton
      component="a"
      href={item.href}
      p={8}
      style={{
        display: "flex",
        alignItems: collapsed ? "center" : undefined,
        justifyContent: collapsed ? "center" : undefined,
        gap: 10,
        borderRadius: "var(--mantine-radius-sm)",
        backgroundColor: active ? "var(--mantine-color-dark-5)" : undefined,
      }}
    >
      <item.icon
        size={20}
        color={active ? "var(--mantine-color-steel-5)" : "var(--mantine-color-dimmed)"}
        style={{ flexShrink: 0 }}
      />
      {!collapsed && (
        <Text size="sm" c={active ? "steel.5" : "dimmed"} style={{ whiteSpace: "nowrap" }}>
          {item.label}
        </Text>
      )}
    </UnstyledButton>
  );

  if (collapsed) {
    return (
      <Tooltip label={item.label} position="right" withArrow>
        {content}
      </Tooltip>
    );
  }

  return content;
}
