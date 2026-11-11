import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import {
  apiRequest,
  type CustomPromptRegistration,
  type PromptRegistryCharacterLora,
  type PromptRegistryHeatmap,
  type PromptRegistryEntry,
  type PromptRegistryLookup,
  type PromptRegistryMedia,
} from "../lib/api";
import { PromptRegistryHeatmap as PromptRegistryHeatmapView } from "../components/prompt-registry-heatmap";
import { MediaFavoriteButton } from "../components/media-favorite-button";
import { usePersistedState } from "../lib/use-persisted-state";
import { useMediaOverlay } from "../lib/use-media-overlay";
import { MediaOverlayHost } from "../components/media-overlay-host";
import { browseDetailHref, browsePageQuery } from "../lib/media-browse";
import { mediaPageSize, parseOffset } from "../lib/media-view";

type PromptIdParts = {
  source: string;
  index: string;
};

type PromptSelectionContext = {
  source: "heatmap" | "lookup";
  characterLora: string | null;
};

type PromptRegistryMediaGroup = {
  key: string;
  label: string;
  media: PromptRegistryMedia[];
};

type PromptRegistryCreateResult = {
  promptId: string;
};

const PROMPT_ID_PATTERN = /^\s*(.+?)\s*-\s*(\d+)\s*$/;

const heatmapIncludeNotFavedKey =
  "comfy-gallery.prompt-heatmap.include-not-faved";
const heatmapIncludeTrashKey = "comfy-gallery.prompt-heatmap.include-trash";
const heatmapCharacterLoraKey =
  "comfy-gallery.prompt-heatmap.character-lora";
const isBooleanPreference = (value: unknown): value is boolean =>
  typeof value === "boolean";
const isStringPreference = (value: unknown): value is string =>
  typeof value === "string";
const UNDEFINED_CHARACTER_LORA_KEY = "__undefined__";
const UNDEFINED_CHARACTER_LORA_LABEL = "Undefined character LoRA";

function characterLoraKey(value: string | null): string {
  const normalized = value?.trim().toLocaleLowerCase();
  return normalized || UNDEFINED_CHARACTER_LORA_KEY;
}

function characterLoraLabel(value: string | null): string {
  const normalized = value?.trim();
  return normalized || UNDEFINED_CHARACTER_LORA_LABEL;
}

function groupMediaByCharacterLora(
  media: PromptRegistryMedia[],
): PromptRegistryMediaGroup[] {
  const groups = new Map<string, PromptRegistryMediaGroup>();
  for (const item of media) {
    const key = characterLoraKey(item.character_lora);
    const group = groups.get(key);
    if (group) {
      group.media.push(item);
    } else {
      groups.set(key, {
        key,
        label: characterLoraLabel(item.character_lora),
        media: [item],
      });
    }
  }
  // The server globally groups before pagination; preserve its navigation order.
  return [...groups.values()];
}

function parsePromptId(value: string): PromptIdParts | null {
  const match = PROMPT_ID_PATTERN.exec(value);
  if (!match) return null;
  const source = match[1].trim();
  return source ? { source, index: match[2] } : null;
}

function shiftPromptId(value: string, delta: -1 | 1): string | null {
  const parsed = parsePromptId(value);
  if (!parsed) return null;
  const nextIndex = BigInt(parsed.index) + BigInt(delta);
  if (nextIndex < 0n) return null;
  return `${parsed.source} - ${nextIndex.toString().padStart(parsed.index.length, "0")}`;
}

export function PromptRegistryPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const promptId = searchParams.get("prompt_id") ?? "";
  const [source, setSource] = useState("");
  const [index, setIndex] = useState("");
  const [registerSource, setRegisterSource] = useState("");
  const [registerIndex, setRegisterIndex] = useState("");
  const [registrationMode, setRegistrationMode] = useState<"manual" | "custom">("manual");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const preferredCharacterLora = searchParams.get("preferred_character_lora");
  const usageOffset = parseOffset(searchParams.get("usage_offset"));
  const returnMediaId = searchParams.get("return_media");
  const restoredReturnRef = useRef("");
  const overlay = useMediaOverlay("prompt");
  const [heatmapSource, setHeatmapSource] = usePersistedState("comfy-gallery.prompt-heatmap.source", "", isStringPreference);
  const [heatmapCharacterLora, setHeatmapCharacterLora] = usePersistedState(
    heatmapCharacterLoraKey,
    "",
    isStringPreference,
  );
  const [heatmapIncludeNotFaved, setHeatmapIncludeNotFaved] = usePersistedState(
    heatmapIncludeNotFavedKey,
    false,
    isBooleanPreference,
  );
  const [heatmapIncludeTrash, setHeatmapIncludeTrash] = usePersistedState(
    heatmapIncludeTrashKey,
    false,
    isBooleanPreference,
  );

  const sourceOptions = useQuery({
    queryKey: ["prompt-registry-source-options"],
    queryFn: () => apiRequest<string[]>("/api/v1/prompt-registry/sources?limit=50"),
    staleTime: 30_000,
  });
  const sourceOptionsWithCustom = [...(sourceOptions.data ?? [])];
  if (!sourceOptionsWithCustom.some((option) => option.trim().toLocaleLowerCase() === "custom")) {
    sourceOptionsWithCustom.push("custom");
  }
  const characterLoraOptions = useQuery({
    queryKey: ["prompt-registry-character-loras"],
    queryFn: () =>
      apiRequest<PromptRegistryCharacterLora[]>(
        "/api/v1/prompt-registry/character-loras?limit=100",
      ),
    staleTime: 60_000,
  });
  const usageSearch = browsePageQuery("prompt", searchParams).toString();
  const lookup = useQuery({
    queryKey: ["prompt-registry-usage", usageSearch],
    queryFn: () =>
      apiRequest<PromptRegistryLookup>(
        `/api/v1/prompt-registry/lookup?${usageSearch}`,
      ),
    enabled: Boolean(promptId.trim()),
    staleTime: 30_000,
  });
  useLayoutEffect(() => {
    if (overlay.mediaId) { restoredReturnRef.current = ""; return; }
    if (overlay.restoring || !returnMediaId || !lookup.data) return;
    const key = `${usageSearch}:${returnMediaId}`;
    if (restoredReturnRef.current === key) return;
    const card = document.getElementById(`prompt-media-${returnMediaId}`);
    if (!card) return;
    restoredReturnRef.current = key;
    const bounds = card.getBoundingClientRect();
    if (bounds.top < 0 || bounds.bottom > window.innerHeight) card.scrollIntoView({ block: "center" });
    card.focus({ preventScroll: true });
  }, [lookup.data, usageSearch, returnMediaId, overlay.mediaId, overlay.restoring]);
  const heatmap = useQuery({
    queryKey: [
      "prompt-registry-heatmap",
      heatmapSource,
      heatmapCharacterLora,
      heatmapIncludeNotFaved,
      heatmapIncludeTrash,
    ],
    queryFn: () => {
      const params = new URLSearchParams({ limit: "20000" });
      if (heatmapSource) params.set("source", heatmapSource);
      if (heatmapCharacterLora) params.set("character_lora", heatmapCharacterLora);
      if (heatmapIncludeNotFaved) params.set("include_not_faved", "true");
      if (heatmapIncludeTrash) params.set("include_trash", "true");
      return apiRequest<PromptRegistryHeatmap>(
        `/api/v1/prompt-registry/heatmap?${params.toString()}`,
      );
    },
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (
      !heatmapCharacterLora ||
      characterLoraOptions.isPending ||
      !characterLoraOptions.data
    ) {
      return;
    }
    if (
      !characterLoraOptions.data.some(
        (option) => option.name === heatmapCharacterLora,
      )
    ) {
      setHeatmapCharacterLora("");
    }
  }, [
    characterLoraOptions.data,
    characterLoraOptions.isPending,
    heatmapCharacterLora,
    setHeatmapCharacterLora,
  ]);

  const create = useMutation({
    mutationFn: async (): Promise<PromptRegistryCreateResult> => {
      if (registrationMode === "custom") {
        const result = await apiRequest<CustomPromptRegistration>(
          "/api/v1/prompt-registry/custom",
          {
            method: "POST",
            body: JSON.stringify({
              prompt,
              negative_prompt: negativePrompt.trim() ? negativePrompt : null,
              origin: "comfy-gallery",
            }),
          },
        );
        return { promptId: result.prompt_id };
      }
      const entry = await apiRequest<PromptRegistryEntry>("/api/v1/prompt-registry", {
        method: "POST",
        body: JSON.stringify({
          source: registerSource.trim(),
          index: registerIndex.trim(),
          prompt,
          negative_prompt: negativePrompt.trim() || null,
        }),
      });
      return { promptId: `${entry.source} - ${entry.index}` };
    },
    onSuccess: async ({ promptId: registeredPromptId }) => {
      setShowRegister(false);
      selectPrompt(registeredPromptId);
      setRegisterSource("");
      setRegisterIndex("");
      setPrompt("");
      setNegativePrompt("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-source-options"] }),
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-lookup"] }),
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-usage"] }),
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-heatmap"] }),
      ]);
    },
  });
  const invalidateRegistryViews = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["prompt-registry-source-options"] }),
      queryClient.invalidateQueries({ queryKey: ["prompt-registry-lookup"] }),
      queryClient.invalidateQueries({ queryKey: ["prompt-registry-usage"] }),
      queryClient.invalidateQueries({ queryKey: ["prompt-registry-heatmap"] }),
      queryClient.invalidateQueries({ queryKey: ["prompt-registry-stats"] }),
    ]);
  };
  const archiveCustomPrompt = useMutation({
    mutationFn: (entryId: string) =>
      apiRequest<void>(`/api/v1/prompt-registry/${entryId}`, { method: "DELETE" }),
    onSuccess: invalidateRegistryViews,
  });
  const restoreCustomPrompt = useMutation({
    mutationFn: (entryId: string) =>
      apiRequest<PromptRegistryEntry>(`/api/v1/prompt-registry/${entryId}/restore`, {
        method: "POST",
      }),
    onSuccess: invalidateRegistryViews,
  });

  function selectPrompt(
    nextPromptId: string,
    source: PromptSelectionContext["source"] = "lookup",
  ) {
    const normalized = nextPromptId.trim();
    if (!normalized) return;
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("prompt_id", normalized);
      next.delete("q");
      for (const key of ["usage_offset", "return_media", "view_media", "preferred_character_lora"]) next.delete(key);
      if (source === "heatmap" && heatmapCharacterLora) next.set("preferred_character_lora", heatmapCharacterLora);
      return next;
    });
  }

  function clearPrompt() {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("prompt_id");
      for (const key of ["usage_offset", "return_media", "view_media", "preferred_character_lora"]) next.delete(key);
      return next;
    });
  }

  function submitDirectLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = String(new FormData(event.currentTarget).get("prompt_id") ?? "").trim();
    selectPrompt(normalized);
  }

  function seekDirectLookup(delta: -1 | 1) {
    const nextPromptId = shiftPromptId(promptId, delta);
    if (!nextPromptId) return;
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("prompt_id", nextPromptId);
      for (const key of ["usage_offset", "return_media", "view_media", "q"]) next.delete(key);
      return next;
    });
  }

  const previousPromptId = shiftPromptId(promptId, -1);
  const nextPromptId = shiftPromptId(promptId, 1);

  function submitSourceLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedSource = source.trim();
    const normalizedIndex = index.trim();
    if (!normalizedSource || !normalizedIndex) return;
    selectPrompt(`${normalizedSource} - ${normalizedIndex}`);
  }

  return (
    <main className="page registry-page prompt-registry-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Reusable prompt identities · Xanta-compatible</p>
          <h1>Prompt registry</h1>
          <p className="muted">
            Resolve <code>source - index</code> IDs to their prompt definition and every
            media output that used the same library entry.
          </p>
        </div>
        <button
          className="secondary-button"
          type="button"
          onClick={() => setShowRegister((visible) => !visible)}
        >
          {showRegister ? "Close editor" : "Register prompt"}
        </button>
      </header>

      <div className="prompt-registry-layout">
        <aside className="prompt-registry-sidebar">
          <section className="panel prompt-registry-heatmap-panel">
        <div className="prompt-registry-heatmap-heading">
          <div>
            <p className="kicker">Usage at a glance</p>
            <h2>Prompt heatmap</h2>
          </div>
          <div className="prompt-registry-heatmap-filters">
            <label className="prompt-registry-heatmap-source">
              Source
              <select
                value={heatmapSource}
                aria-label="Heatmap source"
                onChange={(event) => setHeatmapSource(event.target.value)}
                disabled={sourceOptions.isPending}
              >
                <option value="">All sources</option>
                {sourceOptionsWithCustom.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="prompt-registry-heatmap-source">
              Character LoRA
              <select
                value={heatmapCharacterLora}
                aria-label="Heatmap character LoRA"
                onChange={(event) => setHeatmapCharacterLora(event.target.value)}
                disabled={
                  characterLoraOptions.isPending ||
                  !characterLoraOptions.data?.length
                }
              >
                <option value="">
                  {characterLoraOptions.isPending
                    ? "Loading characters…"
                    : characterLoraOptions.data?.length
                      ? "All characters"
                      : "No character LoRAs"}
                </option>
                {characterLoraOptions.data?.map((option) => (
                  <option key={option.name} value={option.name}>
                    {option.name} ({option.media_count})
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        {heatmap.error ? (
          <p className="notice error-notice">Could not load the prompt heatmap.</p>
        ) : heatmap.isPending ? (
          <p className="muted">Loading prompt usage…</p>
        ) : heatmap.data ? (
          <PromptRegistryHeatmapView
            data={heatmap.data}
            promptId={promptId}
            includeNotFaved={heatmapIncludeNotFaved}
            includeTrash={heatmapIncludeTrash}
            onIncludeNotFavedChange={setHeatmapIncludeNotFaved}
            onIncludeTrashChange={setHeatmapIncludeTrash}
            onSelectPrompt={(nextPromptId) => selectPrompt(nextPromptId, "heatmap")}
          />
        ) : null}
          </section>

          {showRegister ? (
        <form
          className="panel prompt-registry-editor"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <div>
            <p className="kicker">Registry entry</p>
            <h2>Add a prompt definition</h2>
            <p className="muted">
              Register a reusable prompt definition for Prompt Registry lookup.
            </p>
          </div>
          <label className="prompt-registry-registration-mode">
            Registration mode
            <select
              aria-label="Registration mode"
              value={registrationMode}
              onChange={(event) =>
                setRegistrationMode(event.target.value as "manual" | "custom")
              }
            >
              <option value="manual">Existing source + index</option>
              <option value="custom">Custom prompt · auto-assign ID</option>
            </select>
          </label>
          {registrationMode === "custom" ? (
            <p className="muted prompt-registry-custom-hint">
              CG assigns the next <code>custom - 00001</code> ID. An identical positive and
              negative prompt reuses its existing ID.
            </p>
          ) : null}
          <div className="prompt-registry-editor-grid">
            {registrationMode === "manual" ? (
              <>
                <label>
                  Source
                  <input
                    value={registerSource}
                    onChange={(event) => setRegisterSource(event.target.value)}
                    required
                  />
                </label>
                <label>
                  Index
                  <input
                    value={registerIndex}
                    inputMode="numeric"
                    pattern="[0-9]+"
                    onChange={(event) => setRegisterIndex(event.target.value)}
                    required
                  />
                </label>
              </>
            ) : null}
            <label className="wide-field">
              Positive prompt
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                required={registrationMode === "custom"}
              />
            </label>
            <label className="wide-field">
              Negative prompt
              <textarea
                value={negativePrompt}
                onChange={(event) => setNegativePrompt(event.target.value)}
              />
            </label>
          </div>
          {create.error ? <p className="notice error-notice">Could not save this entry.</p> : null}
          <button className="primary-button" type="submit" disabled={create.isPending}>
            {create.isPending
              ? "Saving…"
              : registrationMode === "custom"
                ? "Register custom prompt"
                : "Save prompt entry"}
          </button>
        </form>
      ) : null}

          <details className="panel prompt-registry-locate" data-testid="prompt-registry-locate">
            <summary data-testid="prompt-registry-locate-summary">
              <span>
                <strong>Locate an entry</strong>
                <small>Direct or source + index lookup</small>
              </span>
              <span className="prompt-registry-locate-chevron" aria-hidden="true">
                +
              </span>
            </summary>
            <div className="prompt-registry-search">
        <div className="prompt-registry-search-intro">
          <div>
            <p className="kicker">Low-frequency lookup</p>
            <h2>Open a prompt definition</h2>
          </div>
          <p className="muted">
            Prompt Registry is indexed by <code>source - index</code>. Open an ID from Media
            Detail, or choose a registered source and enter its index.
          </p>
        </div>
        <div className="prompt-registry-query-grid">
          <form className="prompt-registry-query-card" onSubmit={submitDirectLookup}>
            <div>
              <p className="kicker">Direct lookup</p>
              <h3>Prompt ID</h3>
            </div>
            <label>
              <span className="sr-only">Prompt ID</span>
              <input
                key={promptId}
                name="prompt_id"
                defaultValue={promptId}
                placeholder="e.g. sfw-zimage-por-v3 - 03786"
                spellCheck={false}
              />
            </label>
            <button className="primary-button" type="submit">
              Open prompt
            </button>
            <div className="prompt-registry-navigation" aria-label="Prompt index navigation">
              <button
                className="secondary-button"
                type="button"
                onClick={() => seekDirectLookup(-1)}
                disabled={!previousPromptId}
                title={previousPromptId ?? "Enter a source - index prompt ID first"}
              >
                ← Previous index
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={() => seekDirectLookup(1)}
                disabled={!nextPromptId}
                title={nextPromptId ?? "Enter a source - index prompt ID first"}
              >
                Next index →
              </button>
            </div>
          </form>

          <form className="prompt-registry-query-card" onSubmit={submitSourceLookup}>
            <div>
              <p className="kicker">Structured lookup</p>
              <h3>Source + index</h3>
            </div>
            <div className="prompt-registry-source-fields">
              <label className="prompt-registry-source-field">
                Source
                <select
                  value={source}
                  aria-label="Source"
                  onChange={(event) => setSource(event.target.value)}
                  disabled={sourceOptions.isPending}
                >
                  <option value="">
                    {sourceOptions.isPending ? "Loading sources…" : "Select a source"}
                  </option>
                  {sourceOptionsWithCustom.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
                {sourceOptions.error ? (
                  <small className="notice error-notice">
                    Could not load registered sources.
                  </small>
                ) : null}
                {!sourceOptions.isPending &&
                !sourceOptions.error &&
                sourceOptions.data?.length === 0 ? (
                  <small className="muted">No registered sources yet.</small>
                ) : null}
              </label>
              <label>
                Index
                <input
                  value={index}
                  inputMode="numeric"
                  pattern="[0-9]+"
                  onChange={(event) => setIndex(event.target.value)}
                  placeholder="03786"
                  spellCheck={false}
                />
              </label>
            </div>
            <button
              className="secondary-button"
              type="submit"
              disabled={!source.trim() || !index.trim()}
            >
              Open source + index
            </button>
          </form>
        </div>
            </div>
          </details>
        </aside>

        <div className="prompt-registry-usage-column">
          <div className="prompt-registry-results">
            <PromptRegistryDetail
              lookup={lookup}
              promptId={promptId}
              preferredCharacterLora={preferredCharacterLora}
              onClear={clearPrompt}
              searchParams={searchParams}
              onOpenMedia={overlay.open}
              previousPromptId={previousPromptId}
              nextPromptId={nextPromptId}
              onSeekIndex={seekDirectLookup}
              onArchiveCustomPrompt={(entryId) => archiveCustomPrompt.mutate(entryId)}
              onRestoreCustomPrompt={(entryId) => restoreCustomPrompt.mutate(entryId)}
              archivePending={archiveCustomPrompt.isPending}
              restorePending={restoreCustomPrompt.isPending}
              archiveError={archiveCustomPrompt.isError || restoreCustomPrompt.isError}
            />
            {lookup.data && lookup.data.total_media > mediaPageSize ? <nav className="prompt-usage-pagination" aria-label="Prompt usage pages">
              <button type="button" disabled={usageOffset === 0 || lookup.isFetching} onClick={() => setSearchParams((current) => {
                const next = new URLSearchParams(current); next.set("usage_offset", String(Math.max(0, usageOffset - mediaPageSize))); next.delete("return_media"); return next;
              })}>← Previous page</button>
              <span>{Math.floor(usageOffset / mediaPageSize) + 1} / {Math.ceil(lookup.data.total_media / mediaPageSize)}</span>
              <button type="button" disabled={usageOffset + mediaPageSize >= lookup.data.total_media || lookup.isFetching} onClick={() => setSearchParams((current) => {
                const next = new URLSearchParams(current); next.set("usage_offset", String(usageOffset + mediaPageSize)); next.delete("return_media"); return next;
              })}>Next page →</button>
            </nav> : null}
          </div>
        </div>
      </div>
      <MediaOverlayHost overlay={overlay} />
    </main>
  );
}

function PromptRegistryDetail({
  lookup,
  promptId,
  preferredCharacterLora,
  onClear,
  searchParams,
  onOpenMedia,
  previousPromptId,
  nextPromptId,
  onSeekIndex,
  onArchiveCustomPrompt,
  onRestoreCustomPrompt,
  archivePending,
  restorePending,
  archiveError,
}: {
  lookup: UseQueryResult<PromptRegistryLookup>;
  promptId: string;
  preferredCharacterLora: string | null;
  onClear: () => void;
  searchParams: URLSearchParams;
  onOpenMedia: (id: string) => void;
  previousPromptId: string | null;
  nextPromptId: string | null;
  onSeekIndex: (delta: -1 | 1) => void;
  onArchiveCustomPrompt: (entryId: string) => void;
  onRestoreCustomPrompt: (entryId: string) => void;
  archivePending: boolean;
  restorePending: boolean;
  archiveError: boolean;
}) {
  if (!promptId.trim()) {
    return (
      <section className="panel prompt-registry-detail empty-state">
        <strong>Nothing opened yet</strong>
        <p>Enter a prompt ID, or choose a source and index above to inspect its definition.</p>
      </section>
    );
  }
  if (lookup.error) {
    return (
      <section className="panel prompt-registry-detail empty-state">
        <p className="notice error-notice">Prompt ID could not be parsed or loaded.</p>
        <button className="secondary-button" type="button" onClick={onClear}>
          Back to lookup
        </button>
      </section>
    );
  }
  if (lookup.isPending) {
    return <section className="panel prompt-registry-detail muted">Loading prompt…</section>;
  }
  if (lookup.error || !lookup.data) {
    return (
      <section className="panel prompt-registry-detail">
        <p className="notice error-notice">Prompt ID could not be parsed or loaded.</p>
      </section>
    );
  }
  const { data } = lookup;
  const customEntry = data.entry?.source.trim().toLocaleLowerCase() === "custom";
  const archived = Boolean(data.entry?.archived_at);
  return (
    <section className="panel prompt-registry-detail">
      <header className="prompt-registry-detail-header">
        <div className="prompt-registry-detail-identity">
          <p className="kicker">Resolved prompt ID</p>
          <div className="prompt-registry-detail-id-row">
            <h2>{data.prompt_id}</h2>
            <nav className="prompt-registry-index-seek" aria-label="Prompt index navigation">
              <button type="button" aria-label="Previous prompt index" title={previousPromptId ?? "No previous index"}
                disabled={!previousPromptId} onClick={() => onSeekIndex(-1)}>←</button>
              <button type="button" aria-label="Next prompt index" title={nextPromptId ?? "No next index"}
                disabled={!nextPromptId} onClick={() => onSeekIndex(1)}>→</button>
            </nav>
          </div>
        </div>
        <div className="prompt-registry-detail-actions">
          <span className="status-chip" data-status={archived ? "archived" : data.entry ? "ready" : "partial"}>
            {archived ? "Archived" : data.entry ? "Registered" : "Unregistered"}
          </span>
          {customEntry ? (
            archived ? (
              <button
                className="secondary-button"
                type="button"
                disabled={restorePending}
                onClick={() => onRestoreCustomPrompt(data.entry!.id)}
              >
                {restorePending ? "Restoring…" : "Restore custom prompt"}
              </button>
            ) : (
              <button
                className="secondary-button"
                type="button"
                title="Keeps historical media references. Registering the same text later will receive a new ID."
                disabled={archivePending}
                onClick={() => onArchiveCustomPrompt(data.entry!.id)}
              >
                {archivePending ? "Archiving…" : "Archive custom prompt"}
              </button>
            )
          ) : null}
          <button className="secondary-button" type="button" onClick={onClear}>
            New lookup
          </button>
        </div>
      </header>
      {archiveError ? (
        <p className="notice error-notice">Could not update the custom prompt status.</p>
      ) : null}
      {data.entry ? (
        <>
          {archived ? (
            <p className="muted prompt-registry-archived-hint">
              This definition is archived. Historical media lookups remain available; restore it to reuse this ID.
            </p>
          ) : null}
          <PromptText label="Positive prompt" value={data.entry.prompt} />
          <PromptText label="Negative prompt" value={data.entry.negative_prompt} />
        </>
      ) : (
        <p className="muted">
          This ID is present in workflow evidence, but no prompt definition has been
          registered yet.
        </p>
      )}
      <div className="section-heading prompt-registry-media-heading">
        <div>
          <p className="kicker">Usage</p>
          <h3>Media using this prompt</h3>
        </div>
        <span className="document-count">{data.total_media}</span>
      </div>
      {data.media.length ? (
        <div className="prompt-registry-usage-groups" data-testid="prompt-registry-usage-groups">
          {groupMediaByCharacterLora(data.media).map((group) => {
            const isPriority =
              Boolean(preferredCharacterLora) &&
              group.key === characterLoraKey(preferredCharacterLora);
            return (
              <section
                className={
                  isPriority
                    ? "prompt-registry-usage-group is-priority"
                    : "prompt-registry-usage-group"
                }
                data-testid={`prompt-registry-usage-group-${group.key}`}
                key={group.key}
              >
                <header className="prompt-registry-usage-group-header">
                  <div>
                    <p className="kicker">Character LoRA</p>
                    <h4>{group.label}</h4>
                  </div>
                  <span className="document-count">{group.media.length}</span>
                </header>
                <div className="prompt-registry-media-grid">
                  {group.media.map((media) => (
                    <article
                      className="prompt-registry-usage-card"
                      key={media.id}
                      id={`prompt-media-${media.id}`}
                      tabIndex={-1}
                    >
                      <div
                        className="prompt-registry-media-card-actions"
                        role="group"
                        aria-label="Media actions"
                      >
                        {media.content_rating === "nsfw" ? (
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
                          mediaId={media.id}
                          favorite={media.favorite}
                          className="prompt-registry-media-card-favorite"
                        />
                      </div>
                      <Link
                        className={
                          media.is_trash
                            ? "prompt-registry-media-card is-trash"
                            : "prompt-registry-media-card"
                        }
                        to={browseDetailHref("prompt", searchParams, media.id)}
                        data-return-target={
                          searchParams.get("return_media") === media.id || undefined
                        }
                        onClick={(event) => {
                          if (
                            event.button !== 0 ||
                            event.metaKey ||
                            event.ctrlKey ||
                            event.shiftKey ||
                            event.altKey
                          ) {
                            return;
                          }
                          event.preventDefault();
                          onOpenMedia(media.id);
                        }}
                      >
                        <img src={media.preview_url} alt="" loading="lazy" />
                        <span>
                          <strong>{media.original_filename}</strong>
                          {media.is_trash ? <small>Trash</small> : null}
                        </span>
                      </Link>
                    </article>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      ) : (
        <p className="muted">No media has been matched to this prompt ID yet.</p>
      )}
    </section>
  );
}

function PromptText({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="prompt-registry-text">
      <small>{label}</small>
      <pre>{value}</pre>
    </div>
  );
}
