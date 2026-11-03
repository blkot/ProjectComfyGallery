import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import {
  apiRequest,
  type PromptRegistryCharacterLora,
  type PromptRegistryHeatmap,
  type PromptRegistryEntry,
  type PromptRegistryLookup,
} from "../lib/api";
import { PromptRegistryHeatmap as PromptRegistryHeatmapView } from "../components/prompt-registry-heatmap";
import { usePersistedState } from "../lib/use-persisted-state";

type PromptIdParts = {
  source: string;
  index: string;
};

const PROMPT_ID_PATTERN = /^\s*(.+?)\s*-\s*(\d+)\s*$/;

const heatmapIncludeNotFavedKey =
  "comfy-gallery.prompt-heatmap.include-not-faved";
const heatmapIncludeTrashKey = "comfy-gallery.prompt-heatmap.include-trash";
const isBooleanPreference = (value: unknown): value is boolean =>
  typeof value === "boolean";

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
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const [heatmapSource, setHeatmapSource] = useState("");
  const [heatmapCharacterLora, setHeatmapCharacterLora] = useState("");
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
  const characterLoraOptions = useQuery({
    queryKey: ["prompt-registry-character-loras"],
    queryFn: () =>
      apiRequest<PromptRegistryCharacterLora[]>(
        "/api/v1/prompt-registry/character-loras?limit=100",
      ),
    staleTime: 60_000,
  });
  const lookup = useQuery({
    queryKey: ["prompt-registry-lookup", promptId],
    queryFn: () =>
      apiRequest<PromptRegistryLookup>(
        `/api/v1/prompt-registry/lookup?prompt_id=${encodeURIComponent(promptId)}`,
      ),
    enabled: Boolean(promptId.trim()),
  });
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
  const create = useMutation({
    mutationFn: () =>
      apiRequest<PromptRegistryEntry>("/api/v1/prompt-registry", {
        method: "POST",
        body: JSON.stringify({
          source: registerSource.trim(),
          index: registerIndex.trim(),
          prompt,
          negative_prompt: negativePrompt.trim() || null,
        }),
      }),
    onSuccess: async (entry) => {
      setShowRegister(false);
      selectPrompt(`${entry.source} - ${entry.index}`);
      setRegisterSource("");
      setRegisterIndex("");
      setPrompt("");
      setNegativePrompt("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-source-options"] }),
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-lookup"] }),
      ]);
    },
  });

  function selectPrompt(nextPromptId: string) {
    const normalized = nextPromptId.trim();
    if (!normalized) return;
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("prompt_id", normalized);
      next.delete("q");
      return next;
    });
  }

  function clearPrompt() {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("prompt_id");
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
    if (nextPromptId) selectPrompt(nextPromptId);
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
                disabled={sourceOptions.isPending || !sourceOptions.data?.length}
              >
                <option value="">All sources</option>
                {sourceOptions.data?.map((option) => (
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
            onSelectPrompt={selectPrompt}
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
              Keep the index as written by Xanta Utils so leading zeroes remain visible.
            </p>
          </div>
          <div className="prompt-registry-editor-grid">
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
            <label className="wide-field">
              Positive prompt
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} />
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
            {create.isPending ? "Saving…" : "Save prompt entry"}
          </button>
        </form>
      ) : null}

      <section className="prompt-registry-search panel">
        <div className="prompt-registry-search-intro">
          <div>
            <p className="kicker">Locate an entry</p>
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
                  disabled={sourceOptions.isPending || !sourceOptions.data?.length}
                >
                  <option value="">
                    {sourceOptions.isPending ? "Loading sources…" : "Select a source"}
                  </option>
                  {sourceOptions.data?.map((option) => (
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
      </section>

      <div className="prompt-registry-results">
        <PromptRegistryDetail lookup={lookup} promptId={promptId} onClear={clearPrompt} />
      </div>
    </main>
  );
}

function PromptRegistryDetail({
  lookup,
  promptId,
  onClear,
}: {
  lookup: UseQueryResult<PromptRegistryLookup>;
  promptId: string;
  onClear: () => void;
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
  return (
    <section className="panel prompt-registry-detail">
      <header className="prompt-registry-detail-header">
        <div>
          <p className="kicker">Resolved prompt ID</p>
          <h2>{data.prompt_id}</h2>
        </div>
        <div className="prompt-registry-detail-actions">
          <span className="status-chip" data-status={data.entry ? "ready" : "partial"}>
            {data.entry ? "Registered" : "Unregistered"}
          </span>
          <button className="secondary-button" type="button" onClick={onClear}>
            New lookup
          </button>
        </div>
      </header>
      {data.entry ? (
        <>
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
        <div className="prompt-registry-media-grid">
          {data.media.map((media) => (
            <Link
              className={
                media.is_trash
                  ? "prompt-registry-media-card is-trash"
                  : "prompt-registry-media-card"
              }
              to={`/library/${media.id}`}
              key={media.id}
            >
              <img src={media.preview_url} alt="" loading="lazy" />
              <span>
                <strong>{media.original_filename}</strong>
                <small>
                  {media.is_trash
                    ? "Trash"
                    : `${media.kind}${media.favorite ? " · favorite" : ""}`}
                </small>
              </span>
            </Link>
          ))}
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
