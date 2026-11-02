import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useDeferredValue, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import {
  apiRequest,
  type PromptRegistryEntry,
  type PromptRegistryLookup,
} from "../lib/api";

export function PromptRegistryPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const promptId = searchParams.get("prompt_id") ?? "";
  const [source, setSource] = useState("");
  const [index, setIndex] = useState("");
  const [showSourceSuggestions, setShowSourceSuggestions] = useState(false);
  const [registerSource, setRegisterSource] = useState("");
  const [registerIndex, setRegisterIndex] = useState("");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [showRegister, setShowRegister] = useState(false);
  const deferredSource = useDeferredValue(source);

  const sourceSuggestions = useQuery({
    queryKey: ["prompt-registry-source-suggestions", deferredSource.trim()],
    queryFn: () => {
      const parameters = new URLSearchParams({
        limit: "24",
        q: deferredSource.trim(),
      });
      return apiRequest<string[]>(`/api/v1/prompt-registry/sources?${parameters}`);
    },
    enabled: deferredSource.trim().length >= 2,
    staleTime: 30_000,
  });
  const lookup = useQuery({
    queryKey: ["prompt-registry-lookup", promptId],
    queryFn: () =>
      apiRequest<PromptRegistryLookup>(
        `/api/v1/prompt-registry/lookup?prompt_id=${encodeURIComponent(promptId)}`,
      ),
    enabled: Boolean(promptId.trim()),
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
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-source-suggestions"] }),
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

  function submitSourceLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedSource = source.trim();
    const normalizedIndex = index.trim();
    if (!normalizedSource || !normalizedIndex) return;
    setShowSourceSuggestions(false);
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
            Detail, or enter the source and index directly.
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
          </form>

          <form className="prompt-registry-query-card" onSubmit={submitSourceLookup}>
            <div>
              <p className="kicker">Structured lookup</p>
              <h3>Source + index</h3>
            </div>
            <div className="prompt-registry-source-fields">
              <label className="prompt-registry-source-field">
                Source
                <input
                  value={source}
                  role="combobox"
                  aria-autocomplete="list"
                  aria-controls="prompt-registry-source-options"
                  aria-expanded={showSourceSuggestions}
                  onFocus={() => setShowSourceSuggestions(true)}
                  onChange={(event) => {
                    setSource(event.target.value);
                    setShowSourceSuggestions(true);
                  }}
                  onBlur={() => window.setTimeout(() => setShowSourceSuggestions(false), 120)}
                  placeholder="Search a source"
                  spellCheck={false}
                />
                {showSourceSuggestions && source.trim().length >= 2 ? (
                  <div
                    className="prompt-registry-source-options"
                    id="prompt-registry-source-options"
                    role="listbox"
                  >
                    {sourceSuggestions.isFetching ? (
                      <span className="prompt-registry-source-option muted">Searching…</span>
                    ) : null}
                    {sourceSuggestions.data?.map((option) => (
                      <button
                        type="button"
                        role="option"
                        className="prompt-registry-source-option"
                        key={option}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          setSource(option);
                          setShowSourceSuggestions(false);
                        }}
                      >
                        {option}
                      </button>
                    ))}
                    {!sourceSuggestions.isFetching && sourceSuggestions.data?.length === 0 ? (
                      <span className="prompt-registry-source-option muted">
                        No matching registered source. You can still enter it manually.
                      </span>
                    ) : null}
                  </div>
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
            <Link className="prompt-registry-media-card" to={`/library/${media.id}`} key={media.id}>
              <img src={media.preview_url} alt="" loading="lazy" />
              <span>
                <strong>{media.original_filename}</strong>
                <small>{media.kind}{media.favorite ? " · favorite" : ""}</small>
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
