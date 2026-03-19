import { useState } from "react";
import { AppHeader } from "./AppHeader";
import { AppSidebar, type NavItem } from "./AppSidebar";

interface AppLayoutProps {
  children: React.ReactNode;
  navItems: NavItem[];
}

export function AppLayout({ children, navItems }: AppLayoutProps) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <AppSidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed((c) => !c)}
        navItems={navItems}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <AppHeader />
        <div style={{ flex: 1, overflow: "auto" }}>
          {children}
        </div>
      </div>
    </div>
  );
}
