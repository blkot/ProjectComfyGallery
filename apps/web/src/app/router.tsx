/* eslint-disable react-refresh/only-export-components */
import { lazy, Suspense } from "react";
import { Navigate, Outlet, createBrowserRouter } from "react-router";

import { AppShell } from "../components/app-shell";
import { useSession } from "../features/auth/use-session";

const DashboardPage = lazy(() =>
  import("../pages/dashboard-page").then((module) => ({
    default: module.DashboardPage,
  })),
);
const LoginPage = lazy(() =>
  import("../pages/login-page").then((module) => ({
    default: module.LoginPage,
  })),
);
const TokensPage = lazy(() =>
  import("../pages/tokens-page").then((module) => ({
    default: module.TokensPage,
  })),
);
const LibraryPage = lazy(() =>
  import("../pages/library-page").then((module) => ({
    default: module.LibraryPage,
  })),
);
const ImportsPage = lazy(() =>
  import("../pages/imports-page").then((module) => ({
    default: module.ImportsPage,
  })),
);
const JobsPage = lazy(() =>
  import("../pages/jobs-page").then((module) => ({
    default: module.JobsPage,
  })),
);
const NodeRegistryPage = lazy(() =>
  import("../pages/node-registry-page").then((module) => ({
    default: module.NodeRegistryPage,
  })),
);
const ModelRegistryPage = lazy(() =>
  import("../pages/model-registry-page").then((module) => ({
    default: module.ModelRegistryPage,
  })),
);
const MediaDetailPage = lazy(() =>
  import("../pages/media-detail-page").then((module) => ({
    default: module.MediaDetailPage,
  })),
);
const SlideshowPage = lazy(() =>
  import("../pages/slideshow-page").then((module) => ({
    default: module.SlideshowPage,
  })),
);
const ReviewHomePage = lazy(() =>
  import("../pages/review-home-page").then((module) => ({
    default: module.ReviewHomePage,
  })),
);
const ReviewWorkspacePage = lazy(() =>
  import("../pages/review-workspace-page").then((module) => ({
    default: module.ReviewWorkspacePage,
  })),
);
const AnalysisPage = lazy(() =>
  import("../pages/analysis-page").then((module) => ({
    default: module.AnalysisPage,
  })),
);
const OperationsPage = lazy(() =>
  import("../pages/operations-page").then((module) => ({
    default: module.OperationsPage,
  })),
);
const NotFoundPage = lazy(() =>
  import("../pages/not-found-page").then((module) => ({
    default: module.NotFoundPage,
  })),
);

function RoutePending() {
  return (
    <main className="route-pending" aria-live="polite">
      <span className="spinner" />
      <span>Opening workspace…</span>
    </main>
  );
}

function ProtectedLayout() {
  const session = useSession();

  if (session.isPending) {
    return <RoutePending />;
  }

  if (!session.data) {
    return <Navigate to="/login" replace />;
  }

  return (
    <AppShell user={session.data.user}>
      <Suspense fallback={<RoutePending />}>
        <Outlet />
      </Suspense>
    </AppShell>
  );
}

function PublicLayout() {
  return (
    <Suspense fallback={<RoutePending />}>
      <Outlet />
    </Suspense>
  );
}

function ProtectedPresentationLayout() {
  const session = useSession();

  if (session.isPending) {
    return <RoutePending />;
  }

  if (!session.data) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Suspense fallback={<RoutePending />}>
      <Outlet />
    </Suspense>
  );
}

export const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [{ path: "/login", element: <LoginPage /> }],
  },
  {
    element: <ProtectedLayout />,
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "/dashboard", element: <DashboardPage /> },
      { path: "/library", element: <LibraryPage /> },
      { path: "/library/:mediaId", element: <MediaDetailPage /> },
      { path: "/review", element: <ReviewHomePage /> },
      { path: "/review/:sessionId", element: <ReviewWorkspacePage /> },
      { path: "/analysis", element: <AnalysisPage /> },
      { path: "/analysis/:runId", element: <AnalysisPage /> },
      { path: "/imports", element: <ImportsPage /> },
      { path: "/jobs", element: <JobsPage /> },
      { path: "/operations", element: <OperationsPage /> },
      { path: "/registries", element: <Navigate to="/registries/nodes" replace /> },
      { path: "/registries/nodes", element: <NodeRegistryPage /> },
      { path: "/registries/models", element: <ModelRegistryPage /> },
      { path: "/settings/tokens", element: <TokensPage /> },
    ],
  },
  {
    element: <ProtectedPresentationLayout />,
    children: [{ path: "/slideshow", element: <SlideshowPage /> }],
  },
  { path: "*", element: <NotFoundPage /> },
]);
