import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type PropsWithChildren, useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router";

import { sessionQueryKey } from "../features/auth/use-session";
import { apiRequest, type User } from "../lib/api";

type AppShellProps = PropsWithChildren<{
  user: User;
}>;

type NavigationIcon =
  | "analysis"
  | "dashboard"
  | "imports"
  | "jobs"
  | "library"
  | "models"
  | "nodes"
  | "operations"
  | "review"
  | "tokens";

const navigationGroups: {
  label: string;
  items: { to: string; label: string; icon: NavigationIcon }[];
}[] = [
  {
    label: "Workspace",
    items: [
      { to: "/dashboard", label: "Overview", icon: "dashboard" },
      { to: "/library", label: "Media Library", icon: "library" },
      { to: "/imports", label: "Imports", icon: "imports" },
      { to: "/review", label: "Blind Review", icon: "review" },
      { to: "/analysis", label: "Analysis Lab", icon: "analysis" },
    ],
  },
  {
    label: "System",
    items: [
      { to: "/registries/nodes", label: "Node Registry", icon: "nodes" },
      { to: "/registries/models", label: "Model Registry", icon: "models" },
      { to: "/jobs", label: "Jobs", icon: "jobs" },
      { to: "/operations", label: "Operations", icon: "operations" },
      { to: "/settings/tokens", label: "API Tokens", icon: "tokens" },
    ],
  },
];

const sidebarStorageKey = "comfy-gallery.sidebar-collapsed";

export function AppShell({ children, user }: AppShellProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarCollapsed);
  const logout = useMutation({
    mutationFn: () =>
      apiRequest<void>("/api/v1/auth/logout", { method: "POST" }),
    onSuccess: async () => {
      queryClient.setQueryData(sessionQueryKey, null);
      await queryClient.invalidateQueries();
      navigate("/login", { replace: true });
    },
  });

  useEffect(() => {
    try {
      window.localStorage.setItem(
        sidebarStorageKey,
        sidebarCollapsed ? "true" : "false",
      );
    } catch {
      // The layout remains usable when storage is unavailable.
    }
  }, [sidebarCollapsed]);

  return (
    <div className="app-shell" data-sidebar-collapsed={sidebarCollapsed}>
      <aside className="sidebar">
        <div className="sidebar-header">
          <NavLink className="brand" to="/dashboard" aria-label="ComfyGallery home">
            <span className="brand-mark">CG</span>
            <span className="brand-copy">
              <strong>ComfyGallery</strong>
              <small>Local evidence lab</small>
            </span>
          </NavLink>
          <button
            className="sidebar-toggle"
            type="button"
            aria-controls="primary-navigation"
            aria-expanded={!sidebarCollapsed}
            aria-label={
              sidebarCollapsed ? "Expand navigation" : "Collapse navigation"
            }
            title={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
          >
            <CollapseIcon collapsed={sidebarCollapsed} />
          </button>
        </div>

        <nav
          className="primary-nav"
          id="primary-navigation"
          aria-label="Primary navigation"
        >
          {navigationGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p className="nav-label">{group.label}</p>
              {group.items.map((item) => (
                <NavLink
                  to={item.to}
                  title={sidebarCollapsed ? item.label : undefined}
                  aria-label={sidebarCollapsed ? item.label : undefined}
                  key={item.to}
                >
                  <NavIcon name={item.icon} />
                  <span className="nav-text">{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-block">
            <span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span>
            <span className="user-copy">
              <strong>{user.username}</strong>
              <small>Administrator</small>
            </span>
          </div>
          <button
            className="text-button"
            type="button"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
            aria-label={logout.isPending ? "Signing out" : "Sign out"}
            title={sidebarCollapsed ? "Sign out" : undefined}
          >
            <SignOutIcon />
            <span className="sign-out-copy">
              {logout.isPending ? "Signing out…" : "Sign out"}
            </span>
          </button>
        </div>
      </aside>
      <div className="content-column">{children}</div>
    </div>
  );
}

function readSidebarCollapsed(): boolean {
  try {
    return window.localStorage.getItem(sidebarStorageKey) === "true";
  } catch {
    return false;
  }
}

function CollapseIcon({ collapsed }: { collapsed: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16" />
      <path d={collapsed ? "m13 9 3 3-3 3" : "m16 9-3 3 3 3"} />
    </svg>
  );
}

function SignOutIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M10 5H5v14h5" />
      <path d="M13 8l4 4-4 4" />
      <path d="M17 12H9" />
    </svg>
  );
}

function NavIcon({ name }: { name: NavigationIcon }) {
  const paths: Record<NavigationIcon, string[]> = {
    dashboard: ["M4 4h6v6H4z", "M14 4h6v6h-6z", "M4 14h6v6H4z", "M14 14h6v6h-6z"],
    library: ["M4 5h16v14H4z", "M8 9h8", "M8 13h5"],
    imports: ["M12 3v12", "M7 10l5 5 5-5", "M5 20h14"],
    review: ["M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z", "M9.5 12a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0Z"],
    analysis: ["M4 19V9", "M10 19V5", "M16 19v-7", "M22 19H2"],
    nodes: ["M5 5h5v5H5z", "M14 14h5v5h-5z", "M10 7h5a2 2 0 0 1 2 2v5", "M7 10v4a2 2 0 0 0 2 2h5"],
    models: ["M12 3 4 7v10l8 4 8-4V7z", "m4 7 8 4 8-4", "M12 11v10"],
    jobs: ["M4 7h16v12H4z", "M9 7V4h6v3", "M9 12h6"],
    operations: ["M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z", "M12 2v3", "M12 19v3", "m4.9 4.9-2.1-2.1", "m19.2 19.2-2.1-2.1", "M2 12h3", "M19 12h3", "m4.9 19.1-2.1 2.1", "m19.2 4.8-2.1 2.1"],
    tokens: ["M14 7a5 5 0 1 0-1 7l2 2h2v2h2v2h2v-3l-7-7", "M7.5 9.5h.01"],
  };
  return (
    <svg className="nav-icon" aria-hidden="true" viewBox="0 0 24 24">
      {paths[name].map((path) => (
        <path d={path} key={path} />
      ))}
    </svg>
  );
}
