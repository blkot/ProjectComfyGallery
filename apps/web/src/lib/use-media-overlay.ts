import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router";
import { apiRequest, type MediaNavigation, type MediaPage, type PromptRegistryLookup } from "./api";
import { browseDetailHref, browseNavigationPath, browsePageQuery, browseReturnHref, browseScope, browseSlideshowHref, overlayHref, type MediaBrowseKind } from "./media-browse";
import { mediaPageSize } from "./media-view";

export function useMediaOverlay(kind: MediaBrowseKind) {
  const location = useLocation();
  const navigate = useNavigate();
  const navigateRef = useRef(navigate);
  useEffect(() => { navigateRef.current = navigate; }, [navigate]);
  const [search] = useSearchParams();
  const queryClient = useQueryClient();
  const mediaId = search.get("view_media") ?? "";
  const scopeSearch = browseScope(kind, search).toString();
  const navigation = useQuery({
    queryKey: [kind === "library" ? "media-navigation" : "prompt-registry-usage-navigation", mediaId, scopeSearch],
    queryFn: () => apiRequest<MediaNavigation>(browseNavigationPath(kind, mediaId, new URLSearchParams(scopeSearch))),
    enabled: Boolean(mediaId),
    retry: false,
  });
  const last = useRef<{ id: string; search: string; navigation?: MediaNavigation; initialId: string } | null>(null);
  const ownedHistory = useRef(false);
  const [restoreError, setRestoreError] = useState("");
  const [restoring, setRestoring] = useState(false);
  const [notice, setNotice] = useState("");
  const restoreAttempt = useRef<(() => void) | null>(null);

  const pageQuery = useCallback((params: URLSearchParams, position?: number | null) => {
    const query = browsePageQuery(kind, params, position);
    return kind === "library" ? {
      queryKey: ["media", query.toString()],
      queryFn: () => apiRequest<MediaPage>(`/api/v1/media?${query}`),
      staleTime: 30_000,
    } : {
      queryKey: ["prompt-registry-usage", query.toString()],
      queryFn: () => apiRequest<PromptRegistryLookup>(`/api/v1/prompt-registry/lookup?${query}`),
      staleTime: 30_000,
    };
  }, [kind]);

  useEffect(() => {
    if (!mediaId) return;
    const previous = last.current;
    last.current = {
      id: mediaId,
      search: search.toString(),
      initialId: previous?.initialId ?? mediaId,
      navigation: navigation.data ?? (previous?.id === mediaId ? previous.navigation : undefined),
    };
    if (navigation.data) {
      const options = pageQuery(search, navigation.data.position);
      // Prefetch the destination page, not every intervening page.
      void queryClient.prefetchQuery<MediaPage | PromptRegistryLookup>(options);
    }
  }, [mediaId, navigation.data, pageQuery, queryClient, search]);

  useEffect(() => {
    if (mediaId || !last.current) return;
    const closed = last.current;
    last.current = null;
    ownedHistory.current = false;
    let cancelled = false;
    const restore = async () => {
      setRestoring(true);
      setRestoreError("");
      try {
        const params = new URLSearchParams(closed.search);
        let id = closed.id;
        let position = closed.navigation?.position;
        const scope = browseScope(kind, params);
        // Validate by immutable media ID: uploads and mutations can shift offsets.
        try {
          const latest = await apiRequest<MediaNavigation>(browseNavigationPath(kind, id, scope));
          position = latest.position;
        } catch (error) {
          if (!(error instanceof Error) || !("status" in error) || error.status !== 404) throw error;
          let found = false;
          for (const candidate of [closed.navigation?.next_id, closed.navigation?.previous_id]) {
            if (!candidate) continue;
            try {
              const neighbor = await apiRequest<MediaNavigation>(browseNavigationPath(kind, candidate, scope));
              id = candidate;
              position = neighbor.position;
              found = true;
              break;
            } catch { /* Try the other neighbor; never leave the original scope. */ }
          }
          if (!cancelled) setNotice("The last media no longer matches this view.");
          if (!found) {
            id = "";
            position = closed.navigation?.position ?? 1;
          }
        }
        const fetchPage = (targetPosition?: number | null) => queryClient.fetchQuery<MediaPage | PromptRegistryLookup>({
          ...pageQuery(params, targetPosition), staleTime: 0,
        });
        // Refresh in-place, without unmounting the source or hiding its cached grid.
        // A prefetch can be old after uploads shift an item across a page boundary.
        let page = await fetchPage(position);
        let total = "items" in page ? page.total : page.total_media;
        let items = "items" in page ? page.items : page.media;
        if (id && !items.some((item) => item.id === id)) {
          const latest = await apiRequest<MediaNavigation>(browseNavigationPath(kind, id, scope));
          position = latest.position;
          page = await fetchPage(position);
          total = "items" in page ? page.total : page.total_media;
          items = "items" in page ? page.items : page.media;
          if (!items.some((item) => item.id === id)) throw new Error("The view changed while restoring.");
        }
        if (!id && total > 0 && (position ?? 1) > total) {
          position = total;
          page = await fetchPage(position);
          items = "items" in page ? page.items : page.media;
        }
        if (total === 0) position = 1;
        if (!id && items.length) id = items[Math.min(items.length - 1, Math.max(0, ((position ?? 1) - 1) % mediaPageSize))].id;
        const target = new URL(browseReturnHref(kind, params, id, position), "http://gallery.local");
        if (!id) target.searchParams.delete("return_media");
        if (!cancelled) {
          setRestoring(false);
          navigateRef.current(`${target.pathname}${target.search}`, { replace: true, preventScrollReset: true });
          // Only refetch heatmap after a mutation marked it stale.
          void queryClient.refetchQueries({ queryKey: ["prompt-registry-heatmap"], type: "active", stale: true });
        }
      } catch {
        if (!cancelled) setRestoreError("Could not locate the last media. Retry to restore its position.");
      } finally {
        if (!cancelled) setRestoring(false);
      }
    };
    restoreAttempt.current = () => { void restore(); };
    void restore();
    return () => {
      cancelled = true;
      restoreAttempt.current = null;
      setRestoring(false);
      setRestoreError("");
    };
  }, [mediaId, kind, location.key, pageQuery, queryClient]);

  function open(id: string) {
    ownedHistory.current = true;
    last.current = { id, search: search.toString(), initialId: id };
    setNotice("");
    navigate(overlayHref(location.pathname, search, id), { state: { mediaOverlay: true }, preventScrollReset: true });
  }

  function seek(id: string) {
    navigate(overlayHref(location.pathname, search, id), { replace: true, state: location.state, preventScrollReset: true });
  }

  function close() {
    if (ownedHistory.current) navigate(-1);
    else {
      const params = new URLSearchParams(search);
      params.delete("view_media");
      navigate(`${location.pathname}?${params}`, { replace: true, preventScrollReset: true });
    }
  }

  const overlayReturn = overlayHref(location.pathname, search, mediaId);
  const fullDetailHref = browseDetailHref(kind, search, mediaId, navigation.data?.position);
  const civitaiParams = new URLSearchParams({ return_to: overlayReturn });
  return {
    mediaId, navigation, open, seek, close, fullDetailHref,
    slideshowHref: browseSlideshowHref(kind, search, mediaId, overlayReturn),
    civitaiHref: `/library/${mediaId}/civitai-post?${civitaiParams}`,
    restoring, restoreError, notice, retryRestore: () => restoreAttempt.current?.(),
  };
}
