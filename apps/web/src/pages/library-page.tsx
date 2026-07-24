import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";

import {
  apiRequest,
  type Collection,
  type MediaPage,
  type MediaTag,
  type ModelReferencePage,
  type ReviewSession,
  type SavedFilter,
} from "../lib/api";
import { formatBytes, formatDate, formatDuration, titleCase } from "../lib/format";
import {
  defaultMediaSort,
  mediaDetailHref,
  mediaListQuery,
  mediaPageSize,
  parseOffset,
} from "../lib/media-view";

export function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selected, setSelected] = useState<Set<string>>(() => new Set());
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
  const checkpointReferenceId =
    searchParams.get("checkpoint_reference_id") ?? "";
  const loraReferenceId = searchParams.get("lora_reference_id") ?? "";
  const sort = searchParams.get("sort") || defaultMediaSort;
  const offset = parseOffset(searchParams.get("offset"));
  const requestSearch = mediaListQuery(searchParams).toString();

  const media = useQuery({
    queryKey: ["media", requestSearch],
    queryFn: () => apiRequest<MediaPage>(`/api/v1/media?${requestSearch}`),
  });
  const checkpointReferences = useQuery({
    queryKey: ["model-references", "library-checkpoint-options"],
    queryFn: () =>
      apiRequest<ModelReferencePage>(
        "/api/v1/model-references?reference_type=checkpoint&limit=500",
      ),
    staleTime: 60_000,
  });
  const loraReferences = useQuery({
    queryKey: ["model-references", "library-lora-options"],
    queryFn: () =>
      apiRequest<ModelReferencePage>(
        "/api/v1/model-references?reference_type=lora&limit=500",
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
          source_kind: "selection",
          media_ids: [...selected],
          random_limit: selected.size,
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
      if (selected.size) {
        await apiRequest<Collection>(`/api/v1/collections/${collection.id}/items`, {
          method: "POST",
          body: JSON.stringify({ media_ids: [...selected] }),
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
      if (selected.size) {
        await apiRequest<MediaTag>(`/api/v1/tags/${tag.id}/media`, {
          method: "POST",
          body: JSON.stringify({ media_ids: [...selected] }),
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
        body: JSON.stringify({ media_ids: [...selected] }),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["collections"] });
    },
  });
  const applyTag = useMutation({
    mutationFn: () =>
      apiRequest<MediaTag>(`/api/v1/tags/${tagId}/media`, {
        method: "POST",
        body: JSON.stringify({ media_ids: [...selected] }),
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
          expression: {
            kind: kind || null,
            status: status || null,
            workflow_status: workflowStatus || null,
            evaluation_state: evaluationState || null,
            trash: trash ? trash === "true" : null,
            checkpoint_reference_id: checkpointReferenceId || null,
            lora_reference_id: loraReferenceId || null,
          },
        }),
      }),
    onSuccess: async () => {
      setSavedFilterName("");
      await queryClient.invalidateQueries({ queryKey: ["saved-filters"] });
    },
  });

  function changeLibraryParameter(name: string, value: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value) next.set(name, value);
      else next.delete(name);
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
        <label>
          Checkpoint
          <select
            value={checkpointReferenceId}
            onChange={(event) =>
              changeLibraryParameter(
                "checkpoint_reference_id",
                event.target.value,
              )
            }
          >
            <option value="">All checkpoints</option>
            {checkpointReferences.data?.items.map((reference) => (
              <option value={reference.id} key={reference.id}>
                {reference.raw_value} ({reference.occurrence_count})
              </option>
            ))}
          </select>
        </label>
        <label>
          LoRA
          <select
            value={loraReferenceId}
            onChange={(event) =>
              changeLibraryParameter("lora_reference_id", event.target.value)
            }
          >
            <option value="">All LoRAs</option>
            {loraReferences.data?.items.map((reference) => (
              <option value={reference.id} key={reference.id}>
                {reference.raw_value} ({reference.occurrence_count})
              </option>
            ))}
          </select>
        </label>
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
        <div>
          <p className="kicker">Review scope</p>
          <strong>{selected.size} selected</strong>
        </div>
        <button
          className="primary-button"
          type="button"
          disabled={selected.size === 0 || startReview.isPending}
          onClick={() => startReview.mutate()}
        >
          Review selection
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
              selected.size === 0 || !collectionId || addToCollection.isPending
            }
          >
            Add selected
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
            disabled={selected.size === 0 || !tagId || applyTag.isPending}
          >
            Apply selected
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
        <small className="muted">
          {collections.data?.length ?? 0} collections · {tags.data?.length ?? 0} tags
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
            data-selected={selected.has(item.id)}
            key={item.id}
          >
            <label className="media-select">
              <input
                type="checkbox"
                checked={selected.has(item.id)}
                onChange={() => toggleSelected(item.id)}
              />
              <span className="sr-only">Select media</span>
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
