import { Group, Image, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import {
  IconLayoutSidebarLeftCollapse,
  type Icon,
} from "@tabler/icons-react";

export interface NavItem {
  icon: Icon;
  label: string;
  href: string;
}

interface AppSidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  navItems: NavItem[];
  logoHref?: string;
}

export function AppSidebar({ collapsed, onToggle, navItems, logoHref }: AppSidebarProps) {
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
            {logoHref ? (
              <UnstyledButton
                component="a"
                href={logoHref}
                style={{ display: "flex", alignItems: "center", gap: 8, textDecoration: "none" }}
              >
                <Image src="/logo.svg" w={24} h={24} />
                <Text fw={600} size="md" c="dimmed">LLMRP</Text>
              </UnstyledButton>
            ) : (
              <Group gap="xs" style={{ cursor: "default" }}>
                <Image src="/logo.svg" w={24} h={24} />
                <Text fw={600} size="md" c="dimmed">LLMRP</Text>
              </Group>
            )}
            <UnstyledButton onClick={onToggle} p={4} style={{ display: "flex" }}>
              <IconLayoutSidebarLeftCollapse size={20} color="var(--mantine-color-dimmed)" />
            </UnstyledButton>
          </>
        )}
      </Group>

      {/* Nav items */}
      <Stack gap={2} px={4} py="xs" style={{ flex: 1 }}>
        {navItems.map((item) => (
          <SidebarLink key={item.href} item={item} collapsed={collapsed} />
        ))}
      </Stack>
    </nav>
  );
}

function SidebarLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const path = window.location.pathname;
  // Trailing-slash hrefs (like "/admin/") match exactly; others match as prefix
  const exactOnly = item.href.endsWith("/");
  const pathNorm = path.replace(/\/+$/, "");
  const hrefNorm = item.href.replace(/\/+$/, "");
  const active = exactOnly
    ? pathNorm === hrefNorm
    : pathNorm === hrefNorm || pathNorm.startsWith(hrefNorm + "/");

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
