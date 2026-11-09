import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import { MediaFavoriteButton } from "../components/media-favorite-button";
import { MediaOverlayHost } from "../components/media-overlay-host";
import { useMediaOverlay } from "../lib/use-media-overlay";
import { browseDetailHref } from "../lib/media-browse";
import {
  apiRequest,
  type ContentRatingFilter,
  type Collection,
  type MediaArchive,
  type MediaBulkActionResponse,
  type MediaPage,
  type MediaSafetyClassificationBatch,
  type MediaTag,
  type ModelReferenceFilterOption,
  type ReviewSession,
  type SavedFilter,
} from "../lib/api";
import {
  formatBytes,
  formatDate,
  formatDuration,
  titleCase,
} from "../lib/format";
import {
  emptyLibrarySelection,
  isMediaSelected,
  isSelectionActive,
  selectAllMatching as createFilterSelection,
  selectionCount,
  selectionPayload,
  toggleMedia,
  togglePage,
  type LibrarySelection,
} from "../lib/library-selection";
import { hasShortcutModifier, isShortcutBlockedTarget } from "../lib/keyboard";
import {
  defaultMediaSort,
  libraryFilterExpression,
  mediaListQuery,
  mediaPageSize,
  mediaReturnParam,
  pageOffsetForNumber,
  paginationItems,
  parseOffset,
  photoWallHref,
  slideshowHref,
  type ReferenceMatch,
  type SlideshowSource,
} from "../lib/media-view";

const libraryControlsStorageKey =
  "comfy-gallery.library-controls-collapsed-v2";

const mediaTypeFilterOptions = [
  { value: "", label: "All", icon: "all" },
  { value: "image", label: "Images", icon: "image" },
  { value: "video", label: "Videos", icon: "video" },
] as const;

const trashFilterOptions = [
  { value: "false", label: "Exclude", icon: "exclude" },
  { value: "all", label: "Include", icon: "include" },
  { value: "true", label: "Only", icon: "only" },
] as const;

const favoriteFilterOptions = [
  { value: "", label: "All", icon: "all" },
  { value: "true", label: "Favorites", icon: "favorite" },
  { value: "false", label: "Not fav", icon: "not-favorite" },
] as const;

const contentRatingFilterOptions = [
  { value: "", label: "All", icon: "all" },
  { value: "sfw", label: "SFW", icon: "sfw" },
  { value: "nsfw", label: "NSFW", icon: "nsfw" },
] as const;

const spatialPreferenceFilterOptions = [
  { value: "", label: "Any", icon: "all" },
  { value: "true", label: "Spatial", icon: "spatial" },
  { value: "false", label: "2D", icon: "two-d" },
] as const;

const spatialAvailabilityFilterOptions = [
  { value: "", label: "Any", icon: "all" },
  { value: "true", label: "Ready", icon: "ready" },
  { value: "false", label: "Not ready", icon: "not-ready" },
] as const;

type LibraryFilterIconName =
  | "all"
  | "exclude"
  | "favorite"
  | "image"
  | "include"
  | "not-favorite"
  | "not-ready"
  | "nsfw"
  | "only"
  | "ready"
  | "sfw"
  | "spatial"
  | "two-d"
  | "video";

type LibrarySegmentedFilterProps = {
  label: string;
  name: string;
  options: ReadonlyArray<{
    value: string;
    label: string;
    icon: LibraryFilterIconName;
  }>;
  value: string;
  onChange: (value: string) => void;
};

function LibrarySegmentedFilter({
  label,
  name,
  options,
  value,
  onChange,
}: LibrarySegmentedFilterProps) {
  return (
    <fieldset className="library-segmented-filter">
      <legend>{label}</legend>
      <div
        className="library-segmented-options"
        role="radiogroup"
        aria-label={label}
      >
        {options.map((option) => (
          <label
            className="library-segmented-option"
            data-active={value === option.value}
            key={option.value || "all"}
            title={option.label}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span>
              <LibraryFilterIcon name={option.icon} />
              <span className="sr-only">{option.label}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function LibraryFilterIcon({ name }: { name: LibraryFilterIconName }) {
  const commonProps = {
    "aria-hidden": true,
    className: "library-filter-icon",
    viewBox: "0 0 24 24",
  } as const;

  switch (name) {
    case "all":
      return (
        <svg {...commonProps}>
          <circle cx="6" cy="6" r="2" />
          <circle cx="18" cy="6" r="2" />
          <circle cx="6" cy="18" r="2" />
          <circle cx="18" cy="18" r="2" />
        </svg>
      );
    case "image":
      return (
        <svg {...commonProps}>
          <rect x="3" y="4" width="18" height="16" rx="2" />
          <circle cx="8" cy="9" r="1.5" />
          <path d="m4 17 5-5 3 3 2-2 6 6" />
        </svg>
      );
    case "video":
      return (
        <svg {...commonProps}>
          <rect x="3" y="5" width="13" height="14" rx="2" />
          <path d="m16 10 5-3v10l-5-3z" />
        </svg>
      );
    case "exclude":
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="8" />
          <path d="M8 8l8 8" />
        </svg>
      );
    case "include":
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v8M8 12h8" />
        </svg>
      );
    case "only":
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case "favorite":
      return (
        <svg {...commonProps}>
          <path d="M12 20S4 15.5 4 9.5a4.5 4.5 0 0 1 8-2.8 4.5 4.5 0 0 1 8 2.8C20 15.5 12 20 12 20Z" />
        </svg>
      );
    case "not-favorite":
      return (
        <svg {...commonProps}>
          <path d="M12 20S4 15.5 4 9.5a4.5 4.5 0 0 1 8-2.8 4.5 4.5 0 0 1 8 2.8C20 15.5 12 20 12 20Z" />
          <path d="m5 5 14 14" />
        </svg>
      );
    case "sfw":
      return (
        <svg {...commonProps}>
          <path d="M12 3 20 6v5c0 5-3.3 8.2-8 10-4.7-1.8-8-5-8-10V6z" />
          <path d="m8 12 2.5 2.5L16 9" />
        </svg>
      );
    case "nsfw":
      return (
        <svg {...commonProps}>
          <path d="M12 3 20 6v5c0 5-3.3 8.2-8 10-4.7-1.8-8-5-8-10V6z" />
          <path d="M12 8v5M12 16h.01" />
        </svg>
      );
    case "spatial":
      return (
        <svg {...commonProps}>
          <path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z" />
          <path d="m4 7.5 8 4.5 8-4.5M12 12v9" />
        </svg>
      );
    case "two-d":
      return (
        <svg {...commonProps}>
          <rect x="4" y="5" width="16" height="14" rx="2" />
          <path d="m7 15 3-3 2 2 2-2 3 3" />
        </svg>
      );
    case "ready":
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="8" />
          <path d="m8 12 2.5 2.5L16 9" />
        </svg>
      );
    case "not-ready":
      return (
        <svg {...commonProps}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4l3 2" />
        </svg>
      );
  }
}

export function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const galleryTopRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const restoredReturnRef = useRef<string | null>(null);
  const [selection, setSelection] = useState<LibrarySelection>(
    emptyLibrarySelection,
  );
  const [mediaArchiveId, setMediaArchiveId] = useState<string | null>(null);
  const [classificationBatch, setClassificationBatch] =
    useState<MediaSafetyClassificationBatch | null>(null);
  const [collectionName, setCollectionName] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const [tagName, setTagName] = useState("");
  const [tagId, setTagId] = useState("");
  const [savedFilterName, setSavedFilterName] = useState("");
  const [slideshowOpen, setSlideshowOpen] = useState(false);
  const [slideshowSource, setSlideshowSource] =
    useState<SlideshowSource>("filter");
  const [slideshowCollectionId, setSlideshowCollectionId] = useState("");
  const [slideshowShuffle, setSlideshowShuffle] = useState(false);
  const [slideshowInterval, setSlideshowInterval] = useState(8);
  const [controlsCollapsed, setControlsCollapsed] = useState(
    readLibraryControlsCollapsed,
  );
  const controlsCollapseTimeoutRef = useRef<number | null>(null);
  const keywordQuery = searchParams.get("q")?.trim() ?? "";
  const kind = searchParams.get("kind") ?? "";
  const status = searchParams.get("status") ?? "";
  const workflowStatus = searchParams.get("workflow_status") ?? "";
  const evaluationState = searchParams.get("evaluation_state") ?? "";
  const trashParam = searchParams.get("trash");
  const trash =
    trashParam === "all" || trashParam === "true" || trashParam === "false"
      ? trashParam
      : "false";
  const favorite = searchParams.get("favorite") ?? "";
  const contentRating = searchParams.get("content_rating") ?? "";
  const preferSpatialPlayback =
    searchParams.get("prefer_spatial_playback") ??
    searchParams.get("spatial_view_preferred") ??
    "";
  const spatialAvailable = searchParams.get("spatial_available") ?? "";
  const checkpointReferenceIds = searchParams.getAll("checkpoint_reference_id");
  const checkpointReferenceMatch: ReferenceMatch =
    searchParams.get("checkpoint_reference_match") === "all" ? "all" : "any";
  const loraReferenceIds = searchParams.getAll("lora_reference_id");
  const loraReferenceMatch: ReferenceMatch =
    searchParams.get("lora_reference_match") === "all" ? "all" : "any";
  const sort = searchParams.get("sort") || defaultMediaSort;
  const offset = parseOffset(searchParams.get("offset"));
  const returnMediaId = searchParams.get(mediaReturnParam) ?? "";
  const requestSearch = mediaListQuery(searchParams).toString();
  const overlay = useMediaOverlay("library");
  const selectedCount = selectionCount(selection);
  const selectionActive = isSelectionActive(selection);

  const media = useQuery({
    queryKey: ["media", requestSearch],
    queryFn: () => apiRequest<MediaPage>(`/api/v1/media?${requestSearch}`),
    staleTime: 30_000,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) =>
        ["queued", "running"].includes(item.media_safety_assessment?.status ?? ""),
      )
        ? 3_000
        : false,
  });
  const libraryPageCount = Math.max(
    1,
    Math.ceil((media.data?.total ?? 0) / mediaPageSize),
  );
  const currentLibraryPage = Math.min(
    libraryPageCount,
    Math.floor(offset / mediaPageSize) + 1,
  );
  const checkpointReferences = useQuery({
    queryKey: ["model-references", "library-checkpoint-options"],
    queryFn: () =>
      apiRequest<ModelReferenceFilterOption[]>(
        "/api/v1/model-reference-filter-options?reference_type=checkpoint",
      ),
    staleTime: 60_000,
  });
  const loraReferences = useQuery({
    queryKey: ["model-references", "library-lora-options"],
    queryFn: () =>
      apiRequest<ModelReferenceFilterOption[]>(
        "/api/v1/model-reference-filter-options?reference_type=lora",
      ),
    staleTime: 60_000,
  });
  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: () => apiRequest<Collection[]>("/api/v1/collections"),
  });
  const tags = useQuery({
    queryKey: ["tags"],
    queryFn: () => apiRequest<MediaTag[]>("/api/v1/tags"),
  });
  const startReview = useMutation({
    mutationFn: () =>
      apiRequest<ReviewSession>("/api/v1/review-sessions", {
        method: "POST",
        body: JSON.stringify({
          source_kind: selection.mode === "filter" ? "filter" : "selection",
          media_ids:
            selection.mode === "explicit" ? [...selection.mediaIds] : [],
          filter: selection.mode === "filter" ? selection.filter : null,
          exclude_media_ids:
            selection.mode === "filter"
              ? [...selection.excludedIds]
              : undefined,
          random_limit: Math.min(selectedCount, 2000),
          ordering_mode: "stable",
          optional_modules: [],
        }),
      }),
    onSuccess: (reviewSession) => navigate(`/review/${reviewSession.id}`),
  });
  const createCollection = useMutation({
    mutationFn: async () => {
      const collection = await apiRequest<Collection>("/api/v1/collections", {
        method: "POST",
        body: JSON.stringify({ name: collectionName, description: null }),
      });
      if (selectedCount) {
        await apiRequest<Collection>(
          `/api/v1/collections/${collection.id}/items`,
          {
            method: "POST",
            body: JSON.stringify(selectionPayload(selection)),
          },
        );
      }
      return collection;
    },
    onSuccess: async () => {
      setCollectionName("");
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
  const createTag = useMutation({
    mutationFn: async () => {
      const tag = await apiRequest<MediaTag>("/api/v1/tags", {
        method: "POST",
        body: JSON.stringify({ name: tagName, color: null }),
      });
      if (selectedCount) {
        await apiRequest<MediaTag>(`/api/v1/tags/${tag.id}/media`, {
          method: "POST",
          body: JSON.stringify(selectionPayload(selection)),
        });
      }
      return tag;
    },
    onSuccess: async () => {
      setTagName("");
      await queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
  const addToCollection = useMutation({
    mutationFn: () =>
      apiRequest<Collection>(`/api/v1/collections/${collectionId}/items`, {
        method: "POST",
        body: JSON.stringify(selectionPayload(selection)),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
  const applyTag = useMutation({
    mutationFn: () =>
      apiRequest<MediaTag>(`/api/v1/tags/${tagId}/media`, {
        method: "POST",
        body: JSON.stringify(selectionPayload(selection)),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["tags"] });
    },
  });
  const saveFilter = useMutation({
    mutationFn: () =>
      apiRequest<SavedFilter>("/api/v1/saved-filters", {
        method: "POST",
        body: JSON.stringify({
          name: savedFilterName,
          expression: libraryFilterExpression(searchParams),
        }),
      }),
    onSuccess: async () => {
      setSavedFilterName("");
      await queryClient.invalidateQueries({ queryKey: ["saved-filters"] });
    },
  });
  const bulkFavorite = useMutation({
    mutationFn: (favorite: boolean) =>
      apiRequest<MediaBulkActionResponse>("/api/v1/media/bulk/favorite", {
        method: "POST",
        body: JSON.stringify({ ...selectionPayload(selection), favorite }),
      }),
    onSuccess: async () => {
      clearSelection();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
      ]);
    },
  });
  const bulkContentRating = useMutation({
    mutationFn: (nextRating: ContentRatingFilter | null) =>
      apiRequest<MediaBulkActionResponse>(
        "/api/v1/media/bulk/content-rating",
        {
          method: "POST",
          body: JSON.stringify({
            ...selectionPayload(selection),
            content_rating: nextRating,
          }),
        },
      ),
    onSuccess: async () => {
      clearSelection();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
      ]);
    },
  });
  const bulkTrash = useMutation({
    mutationFn: (isTrash: boolean) =>
      apiRequest<MediaBulkActionResponse>("/api/v1/media/bulk/trash", {
        method: "POST",
        body: JSON.stringify({ ...selectionPayload(selection), is_trash: isTrash }),
      }),
    onSuccess: async () => {
      clearSelection();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["media"] }),
        queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
        queryClient.invalidateQueries({ queryKey: ["review-summary"] }),
        queryClient.invalidateQueries({ queryKey: ["review-sessions"] }),
      ]);
    },
  });
  const mediaArchive = useQuery({
    queryKey: ["media-archive", mediaArchiveId],
    queryFn: () =>
      apiRequest<MediaArchive>(`/api/v1/media/bulk/download/${mediaArchiveId}`),
    enabled: Boolean(mediaArchiveId),
    refetchInterval: (query) =>
      query.state.data && ["queued", "running"].includes(query.state.data.status)
        ? 1_500
        : false,
  });
  const createMediaArchive = useMutation({
    mutationFn: () =>
      apiRequest<MediaArchive>("/api/v1/media/bulk/download", {
        method: "POST",
        body: JSON.stringify(selectionPayload(selection)),
      }),
    onSuccess: (archive) => setMediaArchiveId(archive.id),
  });
  const classifySelectedMedia = useMutation({
    mutationFn: () =>
      apiRequest<MediaSafetyClassificationBatch>(
        "/api/v1/media/bulk/nsfw-classification",
        {
          method: "POST",
          body: JSON.stringify({ ...selectionPayload(selection), force: true }),
        },
      ),
    onSuccess: async (result) => {
      setClassificationBatch(result);
      clearSelection();
      await queryClient.invalidateQueries({ queryKey: ["media"] });
    },
  });

  useLayoutEffect(() => {
    if (overlay.mediaId || overlay.restoring || !returnMediaId || !media.data?.items.length) return;
    const restorationKey = `${requestSearch}:${returnMediaId}`;
    if (restoredReturnRef.current === restorationKey) return;

    const card = document.getElementById(`media-${returnMediaId}`);
    if (!card) return;

    restoredReturnRef.current = restorationKey;
    const bounds = card.getBoundingClientRect();
    if (bounds.top < 0 || bounds.bottom > window.innerHeight) card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
  }, [media.data?.items, requestSearch, returnMediaId, overlay.mediaId, overlay.restoring]);

  useEffect(() => {
    if (overlay.mediaId) restoredReturnRef.current = null;
  }, [overlay.mediaId]);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        libraryControlsStorageKey,
        controlsCollapsed ? "true" : "false",
      );
    } catch {
      // The Library remains usable when storage is unavailable.
    }
  }, [controlsCollapsed]);

  const clearControlsCollapseTimeout = useCallback(() => {
    if (controlsCollapseTimeoutRef.current === null) return;
    window.clearTimeout(controlsCollapseTimeoutRef.current);
    controlsCollapseTimeoutRef.current = null;
  }, []);

  const scheduleControlsCollapse = useCallback(() => {
    clearControlsCollapseTimeout();
    if (controlsCollapsed) return;
    controlsCollapseTimeoutRef.current = window.setTimeout(() => {
      setControlsCollapsed(true);
      controlsCollapseTimeoutRef.current = null;
    }, 650);
  }, [clearControlsCollapseTimeout, controlsCollapsed]);

  useEffect(
    () => () => clearControlsCollapseTimeout(),
    [clearControlsCollapseTimeout],
  );

  const toggleControls = useCallback(() => {
    clearControlsCollapseTimeout();
    setControlsCollapsed((collapsed) => !collapsed);
  }, [clearControlsCollapseTimeout]);

  const changeOffset = useCallback((nextOffset: number) => {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (nextOffset > 0) next.set("offset", String(nextOffset));
      else next.delete("offset");
      next.delete(mediaReturnParam);
      return next;
    });
    window.requestAnimationFrame(() => {
      galleryTopRef.current?.scrollIntoView?.({ block: "start" });
    });
  }, [setSearchParams]);

  useEffect(() => {
    function handleKeyboardPageNavigation(event: KeyboardEvent) {
      if (
        event.repeat ||
        event.defaultPrevented ||
        hasShortcutModifier(event) ||
        slideshowOpen ||
        overlay.mediaId ||
        isShortcutBlockedTarget(event.target)
      ) {
        return;
      }
      const direction =
        event.key === "ArrowLeft" ? -1 : event.key === "ArrowRight" ? 1 : 0;
      if (!direction) return;
      const nextPage = currentLibraryPage + direction;
      if (nextPage < 1 || nextPage > libraryPageCount) return;
      event.preventDefault();
      changeOffset((nextPage - 1) * mediaPageSize);
    }

    window.addEventListener("keydown", handleKeyboardPageNavigation);
    return () =>
      window.removeEventListener("keydown", handleKeyboardPageNavigation);
  }, [
    changeOffset,
    currentLibraryPage,
    libraryPageCount,
    slideshowOpen,
    overlay.mediaId,
  ]);

  function changeLibraryParameter(name: string, value: string) {
    if (selection.mode === "filter" && name !== "sort") clearSelection();
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      if (name === "prefer_spatial_playback") {
        next.delete("spatial_view_preferred");
      }
      next.delete("offset");
      next.delete(mediaReturnParam);
      return next;
    });
  }

  function changeMultiLibraryParameter(name: string, values: string[]) {
    if (selection.mode === "filter") clearSelection();
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete(name);
      for (const value of values) next.append(name, value);
      next.delete("offset");
      next.delete(mediaReturnParam);
      return next;
    });
  }

  function toggleSelected(id: string) {
    setMediaArchiveId(null);
    setSelection((current) => toggleMedia(current, id));
  }

  function toggleCurrentPage() {
    const pageIds = media.data?.items.map((item) => item.id) ?? [];
    if (!pageIds.length) return;
    setMediaArchiveId(null);
    setSelection((current) => togglePage(current, pageIds));
  }

  function selectAllMatching() {
    const count = media.data?.total ?? 0;
    if (!count) return;
    setMediaArchiveId(null);
    setSelection(createFilterSelection(libraryFilterExpression(searchParams), count));
  }

  function clearSelection() {
    setMediaArchiveId(null);
    setSelection(emptyLibrarySelection());
  }

  function beginSelection() {
    setMediaArchiveId(null);
    setSelection({ mode: "explicit", mediaIds: new Set() });
  }

  function startSlideshow() {
    const href = slideshowHref(searchParams, {
      source: slideshowSource,
      collectionId: slideshowCollectionId,
      shuffle: slideshowShuffle,
      intervalSeconds: slideshowInterval,
    });
    navigate(href);
  }

  const currentPageIds = media.data?.items.map((item) => item.id) ?? [];
  const currentPageSelected =
    currentPageIds.length > 0 &&
    currentPageIds.every((id) => isMediaSelected(selection, id));

  return (
    <main
      className="page library-page"
      aria-keyshortcuts="ArrowLeft ArrowRight"
    >
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Managed originals</p>
          <h1>Media library</h1>
        </div>
        <div className="page-header-actions">
          <button
            className={selectionActive ? "text-button" : "secondary-button"}
            type="button"
            onClick={() =>
              selectionActive
                ? clearSelection()
                : beginSelection()
            }
          >
            {selectionActive ? "Cancel selection" : "Select media"}
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={
              !media.data?.total &&
              !collections.data?.some((collection) => collection.item_count > 0)
            }
            onClick={() => {
              setSlideshowCollectionId(
                (current) => current || collections.data?.[0]?.id || "",
              );
              setSlideshowOpen(true);
            }}
          >
            Start slideshow
          </button>
          <Link
            className="secondary-button link-button"
            to={photoWallHref(searchParams)}
          >
            Photo wall
          </Link>
          <Link className="primary-button link-button" to="/imports">
            Import media
          </Link>
        </div>
      </header>

      {slideshowOpen ? (
        <div className="slideshow-setup-backdrop">
          <section
            className="panel slideshow-setup"
            role="dialog"
            aria-modal="true"
            aria-labelledby="slideshow-setup-title"
          >
            <div>
              <p className="kicker">Hands-off playback</p>
              <h2 id="slideshow-setup-title">Start slideshow</h2>
              <p className="muted">
                Images advance automatically. Videos play with audio when the
                browser allows it, and offer an Enable sound control otherwise.
              </p>
            </div>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                startSlideshow();
              }}
            >
              <fieldset className="slideshow-source-options">
                <legend>Media source</legend>
                <label>
                  <input
                    type="radio"
                    name="slideshow-source"
                    value="filter"
                    checked={slideshowSource === "filter"}
                    onChange={() => setSlideshowSource("filter")}
                  />
                  Current filtered media ({media.data?.total ?? 0})
                </label>
                <label>
                  <input
                    type="radio"
                    name="slideshow-source"
                    value="collection"
                    checked={slideshowSource === "collection"}
                    disabled={!collections.data?.length}
                    onChange={() => setSlideshowSource("collection")}
                  />
                  Collection
                </label>
              </fieldset>
              <label>
                Collection
                <select
                  value={slideshowCollectionId}
                  disabled={slideshowSource !== "collection"}
                  onChange={(event) =>
                    setSlideshowCollectionId(event.target.value)
                  }
                >
                  <option value="">Choose a collection</option>
                  {collections.data?.map((collection) => (
                    <option value={collection.id} key={collection.id}>
                      {collection.name} ({collection.item_count})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Image duration
                <select
                  value={slideshowInterval}
                  onChange={(event) =>
                    setSlideshowInterval(Number(event.target.value))
                  }
                >
                  <option value={5}>5 seconds</option>
                  <option value={8}>8 seconds</option>
                  <option value={12}>12 seconds</option>
                  <option value={20}>20 seconds</option>
                </select>
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={slideshowShuffle}
                  onChange={(event) =>
                    setSlideshowShuffle(event.target.checked)
                  }
                />
                Shuffle this slideshow
              </label>
              <div className="slideshow-setup-actions">
                <button
                  className="text-button"
                  type="button"
                  onClick={() => setSlideshowOpen(false)}
                >
                  Cancel
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={
                    slideshowSource === "collection" &&
                    !slideshowCollectionId
                  }
                >
                  Start
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}

      <div
        className="library-workspace"
        data-controls-collapsed={controlsCollapsed}
      >
        <aside
          className="library-sidebar"
          aria-label="Library controls"
          data-collapsed={controlsCollapsed}
          onPointerEnter={clearControlsCollapseTimeout}
          onPointerLeave={scheduleControlsCollapse}
        >
          <div className="library-sidebar-header">
            <span className="library-sidebar-title">
              <LibraryControlsIcon />
              <span className="library-sidebar-title-copy">
                Library controls
              </span>
            </span>
            <button
              className="library-sidebar-toggle sidebar-toggle"
              type="button"
              aria-controls="library-controls-content"
              aria-expanded={!controlsCollapsed}
              aria-label={
                controlsCollapsed
                  ? "Expand library controls"
                  : "Collapse library controls"
              }
              title={
                controlsCollapsed
                  ? "Expand library controls"
                  : "Collapse library controls"
              }
              onClick={toggleControls}
            >
              <LibraryControlsCollapseIcon collapsed={controlsCollapsed} />
            </button>
          </div>

          <div
            className="library-sidebar-content"
            id="library-controls-content"
            hidden={controlsCollapsed}
          >
          <section className="toolbar" aria-label="Media filters">
            <form
              className="library-keyword-search"
              role="search"
              aria-label="Search media library"
              aria-busy={media.isFetching}
              onSubmit={(event) => {
                event.preventDefault();
                changeLibraryParameter(
                  "q",
                  searchInputRef.current?.value.trim() ?? "",
                );
              }}
            >
              <label htmlFor="library-keyword-query">
                Search entire library
                <input
                  id="library-keyword-query"
                  key={keywordQuery}
                  ref={searchInputRef}
                  type="search"
                  name="q"
                  maxLength={256}
                  defaultValue={keywordQuery}
                  placeholder="Checkpoint, LoRA, or prompt"
                  autoComplete="off"
                />
              </label>
              <div className="library-keyword-actions">
                <button className="secondary-button" type="submit">
                  Search
                </button>
                <button
                  className="text-button"
                  type="button"
                  disabled={!keywordQuery}
                  onClick={() => {
                    if (searchInputRef.current) {
                      searchInputRef.current.value = "";
                      searchInputRef.current.focus();
                    }
                    changeLibraryParameter("q", "");
                  }}
                >
                  Clear
                </button>
              </div>
            </form>
            <LibrarySegmentedFilter
              label="Media type"
              name="library-media-type"
              options={mediaTypeFilterOptions}
              value={kind}
              onChange={(value) => changeLibraryParameter("kind", value)}
            />
            <label>
              Evaluation
              <select
                value={evaluationState}
                onChange={(event) =>
                  changeLibraryParameter("evaluation_state", event.target.value)
                }
              >
                <option value="">All evaluation states</option>
                <option value="not_started">Not started</option>
                <option value="in_progress">In progress</option>
                <option value="complete">Complete</option>
              </select>
            </label>
            <LibrarySegmentedFilter
              label="Trash"
              name="library-trash"
              options={trashFilterOptions}
              value={trash}
              onChange={(value) => changeLibraryParameter("trash", value)}
            />
            <LibrarySegmentedFilter
              label="Favorite"
              name="library-favorite"
              options={favoriteFilterOptions}
              value={favorite}
              onChange={(value) => changeLibraryParameter("favorite", value)}
            />
            <LibrarySegmentedFilter
              label="Content safety"
              name="library-content-rating"
              options={contentRatingFilterOptions}
              value={contentRating}
              onChange={(value) =>
                changeLibraryParameter("content_rating", value)
              }
            />
            <LibrarySegmentedFilter
              label="Spatial preference"
              name="library-spatial-preference"
              options={spatialPreferenceFilterOptions}
              value={preferSpatialPlayback}
              onChange={(value) =>
                changeLibraryParameter("prefer_spatial_playback", value)
              }
            />
            <LibrarySegmentedFilter
              label="Spatial video"
              name="library-spatial-video"
              options={spatialAvailabilityFilterOptions}
              value={spatialAvailable}
              onChange={(value) =>
                changeLibraryParameter("spatial_available", value)
              }
            />
            <label>
              Processing status
              <select
                value={status}
                onChange={(event) =>
                  changeLibraryParameter("status", event.target.value)
                }
              >
                <option value="">All statuses</option>
                <option value="ready">Ready</option>
                <option value="ready_with_warnings">Ready with warnings</option>
                <option value="processing">Processing</option>
                <option value="failed">Failed</option>
              </select>
            </label>
            <label>
              Workflow evidence
              <select
                value={workflowStatus}
                onChange={(event) =>
                  changeLibraryParameter("workflow_status", event.target.value)
                }
              >
                <option value="">All workflow states</option>
                <option value="parsed">Parsed</option>
                <option value="absent">Absent</option>
                <option value="partial">Partial</option>
                <option value="malformed">Malformed</option>
                <option value="failed">Failed</option>
                <option value="unprocessed">Unprocessed</option>
              </select>
            </label>
            <ReferenceMultiFilter
              label="Checkpoint"
              emptyLabel="All checkpoints"
              options={checkpointReferences.data ?? []}
              selectedIds={checkpointReferenceIds}
              match={checkpointReferenceMatch}
              onSelectionChange={(values) =>
                changeMultiLibraryParameter("checkpoint_reference_id", values)
              }
              onMatchChange={(value) =>
                changeLibraryParameter("checkpoint_reference_match", value)
              }
            />
            <ReferenceMultiFilter
              label="LoRA"
              emptyLabel="All LoRAs"
              options={loraReferences.data ?? []}
              selectedIds={loraReferenceIds}
              match={loraReferenceMatch}
              onSelectionChange={(values) =>
                changeMultiLibraryParameter("lora_reference_id", values)
              }
              onMatchChange={(value) =>
                changeLibraryParameter("lora_reference_match", value)
              }
            />
            <label>
              Sort
              <select
                value={sort}
                onChange={(event) =>
                  changeLibraryParameter("sort", event.target.value)
                }
              >
                <option value="file_created_desc">File time · newest</option>
                <option value="file_created_asc">File time · oldest</option>
                <option value="imported_desc">Imported · newest</option>
                <option value="imported_asc">Imported · oldest</option>
                <option value="filename_asc">Filename · A–Z</option>
                <option value="filename_desc">Filename · Z–A</option>
                <option value="size_desc">File size · largest</option>
                <option value="size_asc">File size · smallest</option>
              </select>
            </label>
            <span className="result-count" aria-live="polite">
              {media.isFetching
                ? keywordQuery
                  ? "Searching…"
                  : "Loading…"
                : keywordQuery
                  ? `${media.data?.total ?? 0} matches for “${keywordQuery}”`
                  : `${media.data?.total ?? 0} media`}
            </span>
          </section>

          <section className="panel library-scope-panel">
            <div className="selection-summary">
              <p className="kicker">Review scope</p>
              <strong>
                {selection.mode === "browse"
                  ? "Browse mode"
                  : selection.mode === "filter"
                    ? selection.excludedIds.size
                      ? `${selectedCount} of ${selection.count} matching selected`
                      : `All ${selection.count} matching selected`
                    : `${selectedCount} selected`}
              </strong>
              <small>
                {selection.mode === "filter"
                  ? "Filter-backed · exceptions are retained across pages"
                  : selectionActive
                    ? "Card clicks select media · selection is retained across pages"
                    : "Choose Select media to manage a group"}
              </small>
            </div>
            <div className="selection-actions">
              <button
                className="secondary-button"
                type="button"
                disabled={!currentPageIds.length}
                onClick={toggleCurrentPage}
              >
                {currentPageSelected ? "Clear page" : "Select page"}
              </button>
              <button
                className="secondary-button"
                type="button"
                disabled={!media.data?.total}
                onClick={selectAllMatching}
              >
                Select all {media.data?.total ?? 0} matching
              </button>
              <button
                className="text-button"
                type="button"
                disabled={!selectedCount}
                onClick={clearSelection}
              >
                Clear selection
              </button>
            </div>
            {selectionActive ? (
              <div className="selection-batch-actions" aria-label="Batch media actions">
                <p className="kicker">Manage selected media</p>
                <div>
                  <button
                    className="favorite-batch-button"
                    type="button"
                    disabled={!selectedCount || bulkFavorite.isPending}
                    onClick={() => bulkFavorite.mutate(true)}
                  >
                    ★ Favorite
                  </button>
                  <button
                    className="favorite-batch-button"
                    type="button"
                    disabled={!selectedCount || bulkFavorite.isPending}
                    onClick={() => bulkFavorite.mutate(false)}
                  >
                    ☆ Unfavorite
                  </button>
                  <button
                    className="content-rating-batch-button"
                    data-rating="sfw"
                    type="button"
                    disabled={!selectedCount || bulkContentRating.isPending}
                    onClick={() => bulkContentRating.mutate("sfw")}
                  >
                    Mark SFW
                  </button>
                  <button
                    className="content-rating-batch-button"
                    data-rating="nsfw"
                    type="button"
                    disabled={!selectedCount || bulkContentRating.isPending}
                    onClick={() => bulkContentRating.mutate("nsfw")}
                  >
                    Mark NSFW
                  </button>
                  <button
                    className="trash-batch-button"
                    type="button"
                    disabled={!selectedCount || bulkTrash.isPending}
                    onClick={() => bulkTrash.mutate(true)}
                  >
                    Trash selected
                  </button>
                  <button
                    className="restore-batch-button"
                    type="button"
                    disabled={!selectedCount || bulkTrash.isPending}
                    onClick={() => bulkTrash.mutate(false)}
                  >
                    Restore selected
                  </button>
                  <button
                    className="nsfw-classification-batch-button"
                    type="button"
                    disabled={!selectedCount || classifySelectedMedia.isPending}
                    onClick={() => classifySelectedMedia.mutate()}
                  >
                    {classifySelectedMedia.isPending
                      ? "Queuing AI grading…"
                      : `AI classify ${selectedCount} selected`}
                  </button>
                  <button
                    className="download-batch-button"
                    type="button"
                    disabled={!selectedCount || createMediaArchive.isPending}
                    onClick={() => createMediaArchive.mutate()}
                  >
                    {createMediaArchive.isPending
                      ? "Preparing ZIP…"
                      : selection.mode === "filter"
                        ? `Download all matching (${selectedCount})`
                        : `Download selected (${selectedCount})`}
                  </button>
                </div>
              </div>
            ) : null}
            {mediaArchiveId ? (
              <div
                className="media-archive-status"
                aria-live="polite"
                aria-busy={mediaArchive.isFetching || undefined}
              >
                <p className="kicker">Media download</p>
                {mediaArchive.isPending ? (
                  <small>Preparing ZIP archive…</small>
                ) : mediaArchive.isError ? (
                  <p className="notice error-notice" role="alert">
                    The media archive status could not be loaded.
                  </p>
                ) : mediaArchive.data?.status === "succeeded" ? (
                  <>
                    <small>
                      Ready · {mediaArchive.data.included_count ?? 0} files
                      {mediaArchive.data.skipped_count
                        ? ` · ${mediaArchive.data.skipped_count} skipped`
                        : ""}
                      {mediaArchive.data.byte_size
                        ? ` · ${formatBytes(mediaArchive.data.byte_size)}`
                        : ""}
                    </small>
                    {mediaArchive.data.download_url ? (
                      <a
                        className="secondary-button link-button"
                        href={mediaArchive.data.download_url}
                      >
                        Download ZIP
                      </a>
                    ) : null}
                  </>
                ) : mediaArchive.data?.status === "failed" ? (
                  <p className="notice error-notice" role="alert">
                    {mediaArchive.data.error_message ??
                      "The media archive could not be created."}
                  </p>
                ) : (
                  <small>Archive queued; this panel will update automatically…</small>
                )}
              </div>
            ) : null}
            <button
              className="primary-button"
              type="button"
              disabled={!selectedCount || startReview.isPending}
              onClick={() => startReview.mutate()}
            >
              {selection.mode === "filter"
                ? "Review filtered results"
                : "Review selection"}
            </button>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                createCollection.mutate();
              }}
            >
              <input
                aria-label="New collection name"
                placeholder="Collection name"
                value={collectionName}
                onChange={(event) => setCollectionName(event.target.value)}
              />
              <button
                className="secondary-button"
                type="submit"
                disabled={!collectionName.trim() || createCollection.isPending}
              >
                Save collection
              </button>
            </form>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                addToCollection.mutate();
              }}
            >
              <select
                aria-label="Existing collection"
                value={collectionId}
                onChange={(event) => setCollectionId(event.target.value)}
              >
                <option value="">Existing collection</option>
                {collections.data?.map((collection) => (
                  <option value={collection.id} key={collection.id}>
                    {collection.name} ({collection.item_count})
                  </option>
                ))}
              </select>
              <button
                className="secondary-button"
                type="submit"
                disabled={
                  !selectedCount ||
                  !collectionId ||
                  addToCollection.isPending
                }
              >
                Add scope
              </button>
            </form>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                createTag.mutate();
              }}
            >
              <input
                aria-label="New tag name"
                placeholder="Tag name"
                value={tagName}
                onChange={(event) => setTagName(event.target.value)}
              />
              <button
                className="secondary-button"
                type="submit"
                disabled={!tagName.trim() || createTag.isPending}
              >
                Apply new tag
              </button>
            </form>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                applyTag.mutate();
              }}
            >
              <select
                aria-label="Existing tag"
                value={tagId}
                onChange={(event) => setTagId(event.target.value)}
              >
                <option value="">Existing tag</option>
                {tags.data?.map((tag) => (
                  <option value={tag.id} key={tag.id}>
                    {tag.name} ({tag.item_count})
                  </option>
                ))}
              </select>
              <button
                className="secondary-button"
                type="submit"
                disabled={!selectedCount || !tagId || applyTag.isPending}
              >
                Apply scope
              </button>
            </form>
            <form
              onSubmit={(event) => {
                event.preventDefault();
                saveFilter.mutate();
              }}
            >
              <input
                aria-label="Saved filter name"
                placeholder="Saved filter name"
                value={savedFilterName}
                onChange={(event) => setSavedFilterName(event.target.value)}
              />
              <button
                className="secondary-button"
                type="submit"
                disabled={!savedFilterName.trim() || saveFilter.isPending}
              >
                Save current filter
              </button>
            </form>
            <small className="muted scope-footnote">
              {collections.data?.length ?? 0} collections ·{" "}
              {tags.data?.length ?? 0} tags
              {selection.mode === "filter" && selection.count > 2000
                ? " · review sessions use the first 2,000 matching media"
                : ""}
            </small>
          </section>

          {classificationBatch ? (
            <p className="nsfw-classification-result" role="status">
              AI classification queued {classificationBatch.queued_count}
              {classificationBatch.reused_count
                ? ` · ${classificationBatch.reused_count} already in progress`
                : ""}
              {classificationBatch.skipped_count
                ? ` · ${classificationBatch.skipped_count} skipped`
                : ""}
              {classificationBatch.queue_failed_count
                ? ` · ${classificationBatch.queue_failed_count} could not be queued`
                : ""}
            </p>
          ) : null}

          {startReview.error ||
          createCollection.error ||
          createTag.error ||
          addToCollection.error ||
          applyTag.error ||
          saveFilter.error ||
          bulkFavorite.error ||
          bulkContentRating.error ||
          bulkTrash.error ||
          createMediaArchive.error ||
          classifySelectedMedia.error ||
          Boolean(bulkTrash.data?.errors.length) ? (
            <p className="notice error-notice" role="alert">
              {startReview.error?.message ||
                createCollection.error?.message ||
                createTag.error?.message ||
                addToCollection.error?.message ||
                applyTag.error?.message ||
                saveFilter.error?.message ||
                bulkFavorite.error?.message ||
                bulkContentRating.error?.message ||
                bulkTrash.error?.message ||
                createMediaArchive.error?.message ||
                classifySelectedMedia.error?.message ||
                bulkTrash.data?.errors.join(" · ")}
            </p>
          ) : null}
          </div>
        </aside>

        <div className="library-gallery" ref={galleryTopRef}>
          {media.isError ? (
            <p className="notice error-notice" role="alert">
              {keywordQuery
                ? `Search for “${keywordQuery}” could not be completed.`
                : "The media library could not be loaded."}
            </p>
          ) : null}

          {media.data?.items.length === 0 ? (
            <section className="empty-state large-empty">
              <strong>
                {keywordQuery
                  ? `No media matches “${keywordQuery}”`
                  : "No media matches these filters"}
              </strong>
              <p>
                {keywordQuery
                  ? "Try another keyword or clear filters to widen the search."
                  : "Import files from the browser or register a NAS source directory."}
              </p>
            </section>
          ) : null}

          {media.data && media.data.total > mediaPageSize ? (
            <MediaPagination
              offset={offset}
              total={media.data.total}
              position="top"
              onPageChange={changeOffset}
            />
          ) : null}

          <section
            className="media-grid"
            aria-busy={media.isFetching}
            data-selection-mode={selectionActive || undefined}
          >
            {media.data?.items.map((item) => {
              const itemSelected = isMediaSelected(selection, item.id);
              const cardContent = (
                <>
                  <div className="media-preview">
                    {item.status === "ready" ||
                    item.status === "ready_with_warnings" ? (
                      <img
                        src={item.preview_url}
                        alt=""
                        decoding="async"
                        loading="lazy"
                      />
                    ) : (
                      <span>{titleCase(item.status)}</span>
                    )}
                    <div
                      className="media-card-status-stack"
                      role="group"
                      aria-label="Media status"
                    >
                      {item.kind === "video" ? (
                        <span className="media-duration">
                          {formatDuration(item.duration_seconds)}
                        </span>
                      ) : null}
                      {item.spatial_available || item.prefer_spatial_playback ? (
                        <span
                          className="spatial-badge"
                          data-available={item.spatial_available || undefined}
                        >
                          {item.spatial_available && item.prefer_spatial_playback
                            ? "Spatial ready · preferred"
                            : item.spatial_available
                              ? "Spatial ready"
                              : "Spatial preferred"}
                        </span>
                      ) : null}
                      {item.is_trash || item.evaluation_state !== "not_started" ? <span
                        className="evaluation-badge"
                        data-status={item.evaluation_state}
                      >
                        {item.is_trash
                          ? "Trash"
                          : titleCase(item.evaluation_state)}
                      </span> : null}
                      {item.media_safety_assessment ? (
                        <span
                          className="ai-classification-badge"
                          data-status={item.media_safety_assessment.status}
                          title={
                            item.media_safety_assessment.needs_review
                              ? "AI suggestion needs review; the human content rating is unchanged."
                              : "AI suggestion only; the human content rating is unchanged."
                          }
                        >
                          AI {item.media_safety_assessment.status === "completed"
                            ? titleCase(
                                item.media_safety_assessment.needs_review
                                  ? "review"
                                  : item.media_safety_assessment.suggested_rating ??
                                      item.media_safety_assessment.label ??
                                      "classified",
                              )
                            : item.media_safety_assessment.status === "running"
                              ? "Grading"
                              : titleCase(item.media_safety_assessment.status)}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="media-card-body">
                    <div className="media-card-primary-line">
                      <MediaCardFilename filename={item.original_filename} />
                      <time
                        className="media-card-file-time"
                        dateTime={item.file_created_at}
                      >
                        {formatDate(item.file_created_at)}
                      </time>
                    </div>
                    <div className="media-card-secondary-line">
                      <span>
                        {item.width && item.height
                          ? `${item.width} × ${item.height}`
                          : "Unknown size"}
                      </span>
                      <span>{formatBytes(item.byte_size)}</span>
                    </div>
                  </div>
                </>
              );

              return (
                <article
                  className="media-card"
                  data-return-target={returnMediaId === item.id || undefined}
                  data-selected={itemSelected || undefined}
                  id={`media-${item.id}`}
                  key={item.id}
                  tabIndex={-1}
                >
                  {selectionActive ? (
                    <label className="media-select">
                      <input
                        type="checkbox"
                        checked={itemSelected}
                        onChange={() => toggleSelected(item.id)}
                      />
                      <span className="sr-only">
                        {itemSelected ? "Deselect media" : "Select media"}
                      </span>
                    </label>
                  ) : null}
                  {selectionActive ? (
                    <div
                      className="media-card-selection-status"
                      role="group"
                      aria-label="Media status"
                    >
                      {item.favorite ? (
                        <span
                          className="media-card-favorite-badge"
                          role="img"
                          aria-label="Favorited"
                          title="Favorited"
                        >
                          ★
                        </span>
                      ) : null}
                      {item.content_rating === "nsfw" ? (
                        <span
                          className="content-rating-badge"
                          data-rating="nsfw"
                          role="img"
                          title="Content rating: R"
                          aria-label="Content rating: R"
                        >
                          R
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <div
                      className="media-card-actions"
                      role="group"
                      aria-label="Media actions"
                    >
                      {item.content_rating === "nsfw" ? (
                        <span
                          className="content-rating-badge"
                          data-rating="nsfw"
                          role="img"
                          title="Content rating: R"
                          aria-label="Content rating: R"
                        >
                          R
                        </span>
                      ) : null}
                      <MediaFavoriteButton
                        mediaId={item.id}
                        favorite={item.favorite}
                        className="media-card-favorite"
                      />
                    </div>
                  )}
                  {selectionActive ? (
                    <button
                      className="media-card-selection-target"
                      type="button"
                      aria-label={`${itemSelected ? "Deselect" : "Select"} ${item.original_filename}`}
                      aria-pressed={itemSelected}
                      onClick={() => toggleSelected(item.id)}
                    >
                      {cardContent}
                    </button>
                  ) : (
                    <Link
                      to={browseDetailHref("library", searchParams, item.id)}
                      aria-label="Open media record"
                      onClick={(event) => {
                        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                        event.preventDefault();
                        overlay.open(item.id);
                      }}
                    >
                      {cardContent}
                    </Link>
                  )}
                </article>
              );
            })}
          </section>

          {media.data && media.data.total > mediaPageSize ? (
            <MediaPagination
              offset={offset}
              total={media.data.total}
              position="bottom"
              onPageChange={changeOffset}
            />
          ) : null}
        </div>
      </div>
      <MediaOverlayHost overlay={overlay} />
    </main>
  );
}

function MediaCardFilename({ filename }: { filename: string }) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const textRef = useRef<HTMLSpanElement>(null);
  const [overflow, setOverflow] = useState(0);

  const measureOverflow = useCallback(() => {
    const container = containerRef.current;
    const text = textRef.current;
    if (!container || !text) return;
    setOverflow(Math.max(0, text.scrollWidth - container.clientWidth));
  }, []);

  const style = overflow
    ? ({
        "--media-card-filename-shift": `${overflow}px`,
      } as CSSProperties)
    : undefined;

  return (
    <span
      ref={containerRef}
      className="media-card-filename"
      data-overflow={overflow > 0 || undefined}
      title={filename}
      style={style}
      onMouseEnter={measureOverflow}
    >
      <span ref={textRef}>{filename}</span>
    </span>
  );
}

function readLibraryControlsCollapsed(): boolean {
  try {
    const stored = window.localStorage.getItem(libraryControlsStorageKey);
    return stored === null ? true : stored === "true";
  } catch {
    return true;
  }
}

function LibraryControlsIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M4 7h10" />
      <path d="M18 7h2" />
      <path d="M14 4v6" />
      <path d="M4 17h2" />
      <path d="M10 17h10" />
      <path d="M10 14v6" />
    </svg>
  );
}

function LibraryControlsCollapseIcon({
  collapsed,
}: {
  collapsed: boolean;
}) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M15 4v16" />
      <path d={collapsed ? "m12 9-3 3 3 3" : "m9 9 3 3-3 3"} />
    </svg>
  );
}

function MediaPagination({
  offset,
  total,
  position,
  onPageChange,
}: {
  offset: number;
  total: number;
  position: "top" | "bottom";
  onPageChange: (offset: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / mediaPageSize));
  const currentPage = Math.min(
    pageCount,
    Math.floor(offset / mediaPageSize) + 1,
  );
  const pageItems = paginationItems(currentPage, pageCount);

  return (
    <nav
      className="pagination"
      data-position={position}
      aria-label={`Media pages ${position === "top" ? "above" : "below"} gallery`}
    >
      <button
        className="secondary-button"
        type="button"
        disabled={currentPage === 1}
        onClick={() => onPageChange((currentPage - 2) * mediaPageSize)}
      >
        Previous
      </button>
      <span>
        Page {currentPage} of {pageCount} · {offset + 1}–
        {Math.min(offset + mediaPageSize, total)} of {total}
      </span>
      <div className="pagination-pages" aria-label="Nearby pages">
        {pageItems.map((item) =>
          typeof item === "number" ? (
            <button
              className="pagination-page"
              type="button"
              aria-current={item === currentPage ? "page" : undefined}
              aria-label={`Go to page ${item}`}
              disabled={item === currentPage}
              key={item}
              onClick={() => onPageChange(pageOffsetForNumber(item, total))}
            >
              {item}
            </button>
          ) : (
            <span aria-hidden="true" className="pagination-ellipsis" key={item}>
              …
            </span>
          ),
        )}
      </div>
      <form
        className="page-jump"
        onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const requestedPage = Number.parseInt(String(form.get("page")), 10);
          onPageChange(pageOffsetForNumber(requestedPage, total));
        }}
      >
        <label>
          Go to page
          <input
            aria-label={`Go to page from ${position} pagination`}
            defaultValue={currentPage}
            key={currentPage}
            max={pageCount}
            min={1}
            name="page"
            required
            type="number"
          />
        </label>
        <button className="secondary-button" type="submit">
          Go
        </button>
      </form>
      <button
        className="secondary-button"
        type="button"
        disabled={currentPage === pageCount}
        onClick={() => onPageChange(currentPage * mediaPageSize)}
      >
        Next
      </button>
    </nav>
  );
}

function ReferenceMultiFilter({
  label,
  emptyLabel,
  options,
  selectedIds,
  match,
  onSelectionChange,
  onMatchChange,
}: {
  label: string;
  emptyLabel: string;
  options: ModelReferenceFilterOption[];
  selectedIds: string[];
  match: ReferenceMatch;
  onSelectionChange: (values: string[]) => void;
  onMatchChange: (value: ReferenceMatch) => void;
}) {
  const selectedSet = new Set(selectedIds);
  const selectedOptions = options.filter((option) =>
    selectedSet.has(option.reference_id),
  );
  const summary =
    selectedOptions.length === 0
      ? emptyLabel
      : selectedOptions.length === 1
        ? selectedOptions[0].display_name
        : `${selectedOptions.length} selected · ${match === "all" ? "All" : "Any"}`;

  return (
    <div className="reference-filter">
      <span className="reference-filter-label">{label}</span>
      <details>
        <summary title={summary}>{summary}</summary>
        <div className="reference-filter-menu">
          <div className="reference-filter-heading">
            <strong>{label} matching</strong>
            <button
              className="text-button"
              type="button"
              disabled={selectedIds.length === 0}
              onClick={() => onSelectionChange([])}
            >
              Clear
            </button>
          </div>
          <label>
            Match selected values
            <select
              value={match}
              onChange={(event) =>
                onMatchChange(event.target.value as ReferenceMatch)
              }
            >
              <option value="any">Any selected value (OR)</option>
              <option value="all">Every selected value (AND)</option>
            </select>
          </label>
          <div className="reference-filter-options">
            {options.map((option) => (
              <label key={option.reference_id}>
                <input
                  type="checkbox"
                  checked={selectedSet.has(option.reference_id)}
                  onChange={() => {
                    const next = selectedSet.has(option.reference_id)
                      ? selectedIds.filter((id) => id !== option.reference_id)
                      : [...selectedIds, option.reference_id];
                    onSelectionChange(next);
                  }}
                />
                <span>
                  <strong>{option.display_name}</strong>
                  <small>
                    {option.occurrence_count} workflow uses
                    {option.alias_count > 1
                      ? ` · ${option.alias_count} aliases`
                      : ""}
                  </small>
                </span>
              </label>
            ))}
          </div>
        </div>
      </details>
    </div>
  );
}
