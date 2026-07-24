import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type PropsWithChildren } from "react";
import { NavLink, useNavigate } from "react-router";

import { sessionQueryKey } from "../features/auth/use-session";
import { apiRequest, type User } from "../lib/api";

type AppShellProps = PropsWithChildren<{
  user: User;
}>;

export function AppShell({ children, user }: AppShellProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const logout = useMutation({
    mutationFn: () =>
      apiRequest<void>("/api/v1/auth/logout", { method: "POST" }),
    onSuccess: async () => {
      queryClient.setQueryData(sessionQueryKey, null);
      await queryClient.invalidateQueries();
      navigate("/login", { replace: true });
    },
  });

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink className="brand" to="/dashboard" aria-label="ComfyGallery home">
          <span className="brand-mark">CG</span>
          <span>
            <strong>ComfyGallery</strong>
            <small>Local evidence lab</small>
          </span>
        </NavLink>

        <nav className="primary-nav" aria-label="Primary navigation">
          <p className="nav-label">Workspace</p>
          <NavLink to="/dashboard">Overview</NavLink>
          <NavLink to="/library">Media Library</NavLink>
          <NavLink to="/imports">Imports</NavLink>
          <NavLink to="/review">Blind Review</NavLink>
          <NavLink to="/analysis">Analysis Lab</NavLink>
          <p className="nav-label">System</p>
          <NavLink to="/registries/nodes">Node Registry</NavLink>
          <NavLink to="/registries/models">Model Registry</NavLink>
          <NavLink to="/jobs">Jobs</NavLink>
          <NavLink to="/operations">Operations</NavLink>
          <NavLink to="/settings/tokens">API Tokens</NavLink>
        </nav>

        <div className="sidebar-footer">
          <div className="user-block">
            <span className="avatar">{user.username.slice(0, 2).toUpperCase()}</span>
            <span>
              <strong>{user.username}</strong>
              <small>Administrator</small>
            </span>
          </div>
          <button
            className="text-button"
            type="button"
            disabled={logout.isPending}
            onClick={() => logout.mutate()}
          >
            {logout.isPending ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>
      <div className="content-column">{children}</div>
    </div>
  );
}
