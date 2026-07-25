import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import {
  apiRequest,
  type Collection,
  type MediaPage,
  type MediaTag,
  type ModelReferenceFilterOption,
  type ReviewSession,
  type SavedFilter,
} from "../lib/api";
import { formatBytes, formatDate, formatDuration, titleCase } from "../lib/format";
import {
  defaultMediaSort,
  libraryFilterExpression,
  mediaDetailHref,
  mediaListQuery,
  mediaPageSize,
  parseOffset,
  type LibraryFilterExpression,
  type ReferenceMatch,
} from "../lib/media-view";

type FilteredSelection = {
  count: number;
  filter: LibraryFilterExpression;
};

type MembershipPayload =
  | { media_ids: string[] }
  | { filter: LibraryFilterExpression };

export function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
  const [filteredSelection, setFilteredSelection] =
    useState<FilteredSelection | null>(null);
  const [collectionName, setCollectionName] = useState("");
  const [collectionId, setCollectionId] = useState("");
  const [tagName, setTagName] = useState("");
  const [tagId, setTagId] = useState("");
  const [savedFilterName, setSavedFilterName] = useState("");
  const kind = searchParams.get("kind") ?? "";
  const status = searchParams.get("status") ?? "";
  const workflowStatus = searchParams.get("workflow_status") ?? "";
  const evaluationState = searchParams.get("evaluation_state") ?? "";
  const trash = searchParams.get("trash") ?? "";
  const checkpointReferenceIds = searchParams.getAll(
    "checkpoint_reference_id",
  );
  const checkpointReferenceMatch: ReferenceMatch =
    searchParams.get("checkpoint_reference_match") === "all" ? "all" : "any";
  const loraReferenceIds = searchParams.getAll("lora_reference_id");
  const loraReferenceMatch: ReferenceMatch =
    searchParams.get("lora_reference_match") === "all" ? "all" : "any";
  const sort = searchParams.get("sort") || defaultMediaSort;
  const offset = parseOffset(searchParams.get("offset"));
  const requestSearch = mediaListQuery(searchParams).toString();
  const selectionCount = filteredSelection?.count ?? selected.size;

  const media = useQuery({
    queryKey: ["media", requestSearch],
    queryFn: () => apiRequest<MediaPage>(`/api/v1/media?${requestSearch}`),
  });
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
          source_kind: filteredSelection ? "filter" : "selection",
          media_ids: filteredSelection ? [] : [...selected],
          filter: filteredSelection?.filter ?? null,
          random_limit: Math.min(selectionCount, 2000),
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
      if (selectionCount) {
        await apiRequest<Collection>(`/api/v1/collections/${collection.id}/items`, {
          method: "POST",
          body: JSON.stringify(selectionPayload()),
        });
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
      if (selectionCount) {
        await apiRequest<MediaTag>(`/api/v1/tags/${tag.id}/media`, {
          method: "POST",
          body: JSON.stringify(selectionPayload()),
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
        body: JSON.stringify(selectionPayload()),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
  const applyTag = useMutation({
    mutationFn: () =>
      apiRequest<MediaTag>(`/api/v1/tags/${tagId}/media`, {
        method: "POST",
        body: JSON.stringify(selectionPayload()),
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

  function changeLibraryParameter(name: string, value: string) {
    if (name !== "sort") setFilteredSelection(null);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
      next.delete("offset");
      return next;
    });
  }

  function changeMultiLibraryParameter(name: string, values: string[]) {
    setFilteredSelection(null);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete(name);
      for (const value of values) next.append(name, value);
      next.delete("offset");
      return next;
    });
  }

  function changeOffset(nextOffset: number) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (nextOffset > 0) next.set("offset", String(nextOffset));
      else next.delete("offset");
      return next;
    });
  }

  function toggleSelected(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleCurrentPage() {
    const pageIds = media.data?.items.map((item) => item.id) ?? [];
    if (!pageIds.length || filteredSelection) return;
    setSelected((current) => {
      const next = new Set(current);
      const pageIsSelected = pageIds.every((id) => next.has(id));
      for (const id of pageIds) {
        if (pageIsSelected) next.delete(id);
        else next.add(id);
      }
      return next;
    });
  }

  function selectAllMatching() {
    const count = media.data?.total ?? 0;
    if (!count) return;
    setSelected(new Set());
    setFilteredSelection({
      count,
      filter: libraryFilterExpression(searchParams),
    });
  }

  function clearSelection() {
    setSelected(new Set());
    setFilteredSelection(null);
  }

  function selectionPayload(): MembershipPayload {
    return filteredSelection
      ? { filter: filteredSelection.filter }
      : { media_ids: [...selected] };
  }

  const currentPageIds = media.data?.items.map((item) => item.id) ?? [];
  const currentPageSelected =
    currentPageIds.length > 0 && currentPageIds.every((id) => selected.has(id));

  return (
    <main className="page library-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Managed originals</p>
          <h1>Media library</h1>
          <p className="muted">
            Every card represents one content identity. Duplicate paths and filenames
            remain source history, not duplicate media records.
          </p>
        </div>
        <Link className="primary-button link-button" to="/imports">
          Import media
        </Link>
      </header>

      <section className="toolbar" aria-label="Media filters">
        <label>
          Media type
          <select
            value={kind}
            onChange={(event) =>
              changeLibraryParameter("kind", event.target.value)
            }
          >
            <option value="">All types</option>
            <option value="image">Images</option>
            <option value="video">Videos</option>
          </select>
        </label>
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
        <label>
          Trash
          <select
            value={trash}
            onChange={(event) =>
              changeLibraryParameter("trash", event.target.value)
            }
          >
            <option value="">Any disposition</option>
            <option value="false">Exclude Trash</option>
            <option value="true">Trash only</option>
          </select>
        </label>
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
        <span className="result-count">
          {media.isPending ? "Loading…" : `${media.data?.total ?? 0} media`}
        </span>
      </section>

      <section className="panel library-scope-panel">
        <div className="selection-summary">
          <p className="kicker">Review scope</p>
          <strong>
            {filteredSelection
              ? `All ${filteredSelection.count} matching selected`
              : `${selected.size} selected`}
          </strong>
          <small>
            {filteredSelection
              ? "Filter-backed · resolved on the server"
              : "Selection is retained across library pages"}
          </small>
        </div>
        <div className="selection-actions">
          <button
            className="secondary-button"
            type="button"
            disabled={!currentPageIds.length || Boolean(filteredSelection)}
            onClick={toggleCurrentPage}
          >
            {currentPageSelected ? "Clear page" : "Select page"}
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={!media.data?.total || Boolean(filteredSelection)}
            onClick={selectAllMatching}
          >
            Select all {media.data?.total ?? 0} matching
          </button>
          <button
            className="text-button"
            type="button"
            disabled={selectionCount === 0}
            onClick={clearSelection}
          >
            Clear selection
          </button>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={selectionCount === 0 || startReview.isPending}
          onClick={() => startReview.mutate()}
        >
          {filteredSelection ? "Review filtered results" : "Review selection"}
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
              selectionCount === 0 || !collectionId || addToCollection.isPending
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
            disabled={selectionCount === 0 || !tagId || applyTag.isPending}
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
          {collections.data?.length ?? 0} collections · {tags.data?.length ?? 0} tags
          {filteredSelection && filteredSelection.count > 2000
            ? " · review sessions use the first 2,000 matching media"
            : ""}
        </small>
      </section>

      {startReview.error ||
      createCollection.error ||
      createTag.error ||
      addToCollection.error ||
      applyTag.error ||
      saveFilter.error ? (
        <p className="notice error-notice" role="alert">
          {startReview.error?.message ||
            createCollection.error?.message ||
            createTag.error?.message ||
            addToCollection.error?.message ||
            applyTag.error?.message ||
            saveFilter.error?.message}
        </p>
      ) : null}

      {media.isError ? (
        <p className="notice error-notice" role="alert">
          The media library could not be loaded.
        </p>
      ) : null}

      {media.data?.items.length === 0 ? (
        <section className="empty-state large-empty">
          <strong>No media matches these filters</strong>
          <p>Import files from the browser or register a NAS source directory.</p>
        </section>
      ) : null}

      <section className="media-grid" aria-busy={media.isPending}>
        {media.data?.items.map((item) => (
          <article
            className="media-card"
            data-selected={Boolean(filteredSelection) || selected.has(item.id)}
            key={item.id}
          >
            <label className="media-select">
              <input
                type="checkbox"
                checked={Boolean(filteredSelection) || selected.has(item.id)}
                disabled={Boolean(filteredSelection)}
                onChange={() => toggleSelected(item.id)}
              />
              <span className="sr-only">
                {filteredSelection
                  ? "Included by the filtered selection"
                  : "Select media"}
              </span>
            </label>
            <Link
              to={mediaDetailHref(item.id, searchParams)}
              aria-label="Open media record"
            >
              <div className="media-preview">
                {item.status === "ready" ||
                item.status === "ready_with_warnings" ? (
                  <img src={item.preview_url} alt="" loading="lazy" />
                ) : (
                  <span>{titleCase(item.status)}</span>
                )}
                {item.kind === "video" ? (
                  <span className="media-duration">
                    {formatDuration(item.duration_seconds)}
                  </span>
                ) : null}
                {item.warning_count > 0 ? (
                  <span className="warning-badge">Warning</span>
                ) : null}
                <span
                  className="workflow-badge"
                  data-status={item.workflow_status}
                >
                  WF · {titleCase(item.workflow_status)}
                </span>
                <span
                  className="evaluation-badge"
                  data-status={item.evaluation_state}
                >
                  {item.is_trash
                    ? "Trash"
                    : titleCase(item.evaluation_state)}
                </span>
              </div>
              <div className="media-card-body">
                <strong title={item.original_filename}>
                  {item.original_filename}
                </strong>
                <small>
                  {item.width && item.height
                    ? `${item.width} × ${item.height}`
                    : "Unknown size"}
                  {" · "}
                  {formatBytes(item.byte_size)}
                </small>
                <small>
                  {titleCase(item.detected_format ?? item.kind)}
                  {item.source_count
                    ? ` · ${item.source_count} source path(s)`
                    : ""}
                </small>
                <small>File time · {formatDate(item.file_created_at)}</small>
              </div>
            </Link>
          </article>
        ))}
      </section>

      {media.data && media.data.total > mediaPageSize ? (
        <nav className="pagination" aria-label="Media pages">
          <button
            className="secondary-button"
            type="button"
            disabled={offset === 0}
            onClick={() =>
              changeOffset(Math.max(0, offset - mediaPageSize))
            }
          >
            Previous
          </button>
          <span>
            {offset + 1}–
            {Math.min(offset + mediaPageSize, media.data.total)} of{" "}
            {media.data.total}
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={offset + mediaPageSize >= media.data.total}
            onClick={() => changeOffset(offset + mediaPageSize)}
          >
            Next
          </button>
        </nav>
      ) : null}
    </main>
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
