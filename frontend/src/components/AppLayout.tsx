import { useState } from "react";
import { AppHeader } from "./AppHeader";
import { AppSidebar, type NavItem } from "./AppSidebar";

interface AppLayoutProps {
  children: React.ReactNode;
  navItems?: NavItem[];
  logoHref?: string;
  sidebar?: React.ReactNode;
}

export function AppLayout({ children, navItems, logoHref, sidebar }: AppLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      {sidebar ?? (
        <AppSidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed((c) => !c)}
          navItems={navItems ?? []}
          logoHref={logoHref}
        />
      )}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <AppHeader />
        <div style={{ flex: 1, overflow: "auto" }}>
          {children}
        </div>
      </div>
    </div>
  );
}
