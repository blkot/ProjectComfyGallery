import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";

import {
  apiRequest,
  type PromptRegistryEntry,
  type PromptRegistryLookup,
  type PromptRegistryPage,
} from "../lib/api";

export function PromptRegistryPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get("q") ?? "";
  const promptId = searchParams.get("prompt_id") ?? "";
  const [source, setSource] = useState("");
  const [index, setIndex] = useState("");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [showRegister, setShowRegister] = useState(false);

  const entries = useQuery({
    queryKey: ["prompt-registry", search],
    queryFn: () => {
      const parameters = new URLSearchParams({ limit: "48", offset: "0" });
      if (search.trim()) parameters.set("q", search.trim());
      return apiRequest<PromptRegistryPage>(`/api/v1/prompt-registry?${parameters}`);
    },
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
          source: source.trim(),
          index: index.trim(),
          prompt,
          negative_prompt: negativePrompt.trim() || null,
        }),
      }),
    onSuccess: async (entry) => {
      setShowRegister(false);
      selectPrompt(`${entry.source} - ${entry.index}`);
      setSource("");
      setIndex("");
      setPrompt("");
      setNegativePrompt("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["prompt-registry"] }),
        queryClient.invalidateQueries({ queryKey: ["prompt-registry-lookup"] }),
      ]);
    },
  });

  function selectPrompt(nextPromptId: string) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("prompt_id", nextPromptId);
      return next;
    });
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = String(new FormData(event.currentTarget).get("prompt_id") ?? "").trim();
    if (!normalized) return;
    selectPrompt(normalized);
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
              <input value={source} onChange={(event) => setSource(event.target.value)} required />
            </label>
            <label>
              Index
              <input
                value={index}
                inputMode="numeric"
                pattern="[0-9]+"
                onChange={(event) => setIndex(event.target.value)}
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
        <form onSubmit={submitSearch}>
          <label className="wide-field">
            Find prompt ID
            <input
              key={promptId}
              name="prompt_id"
              defaultValue={promptId}
              placeholder="e.g. sfw-zimage-por-v3 - 03786"
            />
          </label>
          <button className="primary-button" type="submit">
            Find media
          </button>
        </form>
        <label className="wide-field">
          Search registry
          <input
            type="search"
            defaultValue={search}
            placeholder="Source, index, or prompt text"
            onChange={(event) => {
              setSearchParams((current) => {
                const next = new URLSearchParams(current);
                if (event.target.value.trim()) next.set("q", event.target.value);
                else next.delete("q");
                return next;
              });
            }}
          />
        </label>
      </section>

      <div className="prompt-registry-layout">
        <section className="prompt-registry-list">
          <div className="section-heading">
            <div>
              <p className="kicker">Definitions</p>
              <h2>Prompt entries</h2>
            </div>
            <span className="document-count">{entries.data?.total ?? "—"}</span>
          </div>
          {entries.error ? <p className="notice error-notice">Registry failed to load.</p> : null}
          <div className="registry-records">
            {entries.data?.items.map((entry) => {
              const id = `${entry.source} - ${entry.index}`;
              return (
                <button
                  className="registry-record"
                  data-selected={promptId === id}
                  type="button"
                  key={entry.id}
                  onClick={() => selectPrompt(id)}
                >
                  <span>
                    <strong>{id}</strong>
                    <small>{entry.prompt || "No positive prompt stored"}</small>
                  </span>
                  <span>
                    <small>{entry.origin}</small>
                    <span className="registry-chips">
                      <em>Open media</em>
                    </span>
                  </span>
                </button>
              );
            })}
            {entries.isPending ? <p className="muted registry-loading">Loading…</p> : null}
            {entries.data?.items.length === 0 ? (
              <div className="empty-state">
                <strong>No registered prompts</strong>
                <p>Register an entry or search an ID directly from a media workflow.</p>
              </div>
            ) : null}
          </div>
        </section>

        <PromptRegistryDetail lookup={lookup} />
      </div>
    </main>
  );
}

function PromptRegistryDetail({
  lookup,
}: {
  lookup: UseQueryResult<PromptRegistryLookup>;
}) {
  if (!lookup.data && !lookup.isPending) {
    return (
      <section className="panel prompt-registry-detail empty-state">
        <strong>Select a prompt ID</strong>
        <p>Choose a registry entry or paste a source - index identifier above.</p>
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
        <span className="status-chip" data-status={data.entry ? "ready" : "partial"}>
          {data.entry ? "Registered" : "Unregistered"}
        </span>
      </header>
      {data.entry ? (
        <>
          <PromptText label="Positive prompt" value={data.entry.prompt} />
          <PromptText label="Negative prompt" value={data.entry.negative_prompt} />
          {data.entry.character_lora ? (
            <div className="prompt-registry-fact">
              <small>Character LoRA</small>
              <code>{data.entry.character_lora}</code>
            </div>
          ) : null}
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
