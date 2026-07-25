import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type FormEvent,
  useDeferredValue,
  useEffect,
  useState,
} from "react";

import {
  apiRequest,
  type NodeDefinitionDetail,
  type NodeDefinitionPage,
  type NodeMappingCreated,
  type RegistrySyncCreated,
  type RegistrySyncRun,
} from "../lib/api";
import {
  RegistryError,
  RegistryPagination,
  RegistryStatusChip,
  RegistrySyncHistory,
  registryPageSize,
} from "../components/registry-shared";
import { titleCase } from "../lib/format";

const terminalStatuses = new Set(["succeeded", "partial", "failed", "cancelled"]);

export function NodeRegistryPage() {
  const queryClient = useQueryClient();
  const [baseUrl, setBaseUrl] = useState("");
  const [search, setSearch] = useState("");
  const [mappingState, setMappingState] = useState("");
  const [presence, setPresence] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);

  const syncRuns = useQuery({
    queryKey: ["registry-sync-runs", "node"],
    queryFn: () =>
      apiRequest<RegistrySyncRun[]>("/api/v1/registry-sync-runs?registry_kind=node"),
    refetchInterval: (query) =>
      query.state.data?.some((run) => !terminalStatuses.has(run.status))
        ? 2_000
        : false,
  });
  const definitions = useQuery({
    queryKey: [
      "node-definitions",
      deferredSearch,
      mappingState,
      presence,
      offset,
    ],
    queryFn: () => {
      const parameters = new URLSearchParams({
        limit: String(registryPageSize),
        offset: String(offset),
      });
      if (deferredSearch.trim()) parameters.set("search", deferredSearch.trim());
      if (mappingState) parameters.set("mapping_state", mappingState);
      if (presence) parameters.set("presence", presence);
      return apiRequest<NodeDefinitionPage>(
        `/api/v1/node-definitions?${parameters.toString()}`,
      );
    },
  });
  const selected = useQuery({
    queryKey: ["node-definition", selectedId],
    queryFn: () =>
      apiRequest<NodeDefinitionDetail>(`/api/v1/node-definitions/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const sync = useMutation({
    mutationFn: () =>
      apiRequest<RegistrySyncCreated>("/api/v1/node-registry/sync", {
        method: "POST",
        body: JSON.stringify({ base_url: baseUrl.trim() || null }),
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["registry-sync-runs"] }),
        queryClient.invalidateQueries({ queryKey: ["jobs"] }),
      ]);
    },
  });

  const activeRun = syncRuns.data?.find((run) => !terminalStatuses.has(run.status));
  useEffect(() => {
    if (!syncRuns.data?.length || activeRun) return;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["node-definitions"] }),
      queryClient.invalidateQueries({ queryKey: ["node-definition"] }),
    ]);
  }, [activeRun, queryClient, syncRuns.data]);

  const error = sync.error ?? definitions.error;

  return (
    <main className="page registry-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Offline interpretation · Phase 3</p>
          <h1>Node registry</h1>
          <p className="muted">
            Cache ComfyUI node schemas, match historical workflows, and correct the
            fields that represent checkpoints, LoRAs, prompts, or parameters.
          </p>
        </div>
        <span className="health-pill" data-state={activeRun ? "wait" : "ok"}>
          <span />
          {activeRun
            ? `${titleCase(activeRun.current_stage ?? "syncing")}…`
            : "Offline cache ready"}
        </span>
      </header>

      {error ? <RegistryError error={error} fallback="The node registry failed." /> : null}

      <section className="panel registry-sync-panel">
        <div>
          <p className="kicker">Live source</p>
          <h2>Refresh from ComfyUI</h2>
          <p className="muted">
            Leave the address blank to use the server setting. A completed snapshot
            remains available when ComfyUI is later offline.
          </p>
        </div>
        <div className="registry-sync-controls">
          <label>
            ComfyUI base URL
            <input
              type="url"
              value={baseUrl}
              placeholder="Configured by the server"
              onChange={(event) => setBaseUrl(event.target.value)}
            />
          </label>
          <button
            className="primary-button"
            type="button"
            disabled={sync.isPending || Boolean(activeRun)}
            onClick={() => sync.mutate()}
          >
            {sync.isPending || activeRun ? "Synchronizing…" : "Sync node registry"}
          </button>
        </div>
      </section>

      <RegistrySyncHistory runs={syncRuns.data ?? []} />

      <section className="section-block">
        <div className="section-heading">
          <div>
            <p className="kicker">Cached definitions</p>
            <h2>Known node types</h2>
          </div>
          <span className="document-count">
            {definitions.data?.total ?? "—"} definitions
          </span>
        </div>
        <div className="registry-toolbar">
          <label className="wide-field">
            Find node
            <input
              type="search"
              value={search}
              placeholder="Class, display name, or module"
              onChange={(event) => {
                setSearch(event.target.value);
                setOffset(0);
              }}
            />
          </label>
          <label>
            Mapping
            <select
              value={mappingState}
              onChange={(event) => {
                setMappingState(event.target.value);
                setOffset(0);
              }}
            >
              <option value="">Any state</option>
              <option value="automatic">Automatic</option>
              <option value="manual">Manually corrected</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
          <label>
            Presence
            <select
              value={presence}
              onChange={(event) => {
                setPresence(event.target.value);
                setOffset(0);
              }}
            >
              <option value="">Live + historical</option>
              <option value="present">Present in ComfyUI</option>
              <option value="historical">Historical only</option>
            </select>
          </label>
        </div>

        <div className="registry-split">
          <div className="registry-records" aria-busy={definitions.isFetching}>
            {definitions.data?.items.map((definition) => (
              <button
                className="registry-record"
                data-selected={selectedId === definition.id}
                type="button"
                key={definition.id}
                onClick={() => setSelectedId(definition.id)}
              >
                <span>
                  <strong>{definition.display_name || definition.class_type}</strong>
                  {definition.display_name ? <code>{definition.class_type}</code> : null}
                </span>
                <span>
                  <small>
                    {definition.category || definition.python_module || "Uncategorized"}
                  </small>
                  <span className="registry-chips">
                    <RegistryStatusChip value={definition.mapping_state} />
                    <RegistryStatusChip
                      value={definition.is_present ? "present" : "historical"}
                    />
                    {definition.workflow_occurrence_count ? (
                      <em>{definition.workflow_occurrence_count} uses</em>
                    ) : null}
                  </span>
                </span>
              </button>
            ))}
            {definitions.isPending ? <p className="muted registry-loading">Loading…</p> : null}
            {definitions.data?.items.length === 0 ? (
              <div className="empty-state">
                <strong>No definitions match</strong>
                <p>Change the filters or synchronize a live ComfyUI instance.</p>
              </div>
            ) : null}
            <RegistryPagination
              offset={offset}
              total={definitions.data?.total ?? 0}
              onChange={setOffset}
            />
          </div>
          <NodeDefinitionPanel
            key={selectedId ?? "empty"}
            detail={selected.data}
            loading={selected.isPending && Boolean(selectedId)}
            onUpdated={async () => {
              await Promise.all([
                queryClient.invalidateQueries({ queryKey: ["node-definitions"] }),
                queryClient.invalidateQueries({
                  queryKey: ["node-definition", selectedId],
                }),
                queryClient.invalidateQueries({ queryKey: ["jobs"] }),
              ]);
            }}
          />
        </div>
      </section>
    </main>
  );
}

function NodeDefinitionPanel({
  detail,
  loading,
  onUpdated,
}: {
  detail: NodeDefinitionDetail | undefined;
  loading: boolean;
  onUpdated: () => Promise<void>;
}) {
  const [locator, setLocator] = useState("");
  const [semanticType, setSemanticType] = useState("checkpoint_reference");
  const [role, setRole] = useState("");
  const [showRaw, setShowRaw] = useState(false);

  const mapping = useMutation({
    mutationFn: () =>
      apiRequest<NodeMappingCreated>("/api/v1/node-mappings", {
        method: "POST",
        body: JSON.stringify({
          node_definition_id: detail?.id,
          locator,
          semantic_type: semanticType,
          role: role.trim() || null,
        }),
      }),
    onSuccess: onUpdated,
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    mapping.mutate();
  }

  if (loading) {
    return <aside className="panel registry-detail"><p className="muted">Loading node…</p></aside>;
  }
  if (!detail) {
    return (
      <aside className="panel registry-detail empty-state">
        <strong>Select a node definition</strong>
        <p>Its schema and correctable semantic mappings will appear here.</p>
      </aside>
    );
  }

  const inputNames = schemaInputNames(detail.input_schema);
  return (
    <aside className="panel registry-detail">
      <p className="kicker">{detail.is_present ? "Live definition" : "Historical evidence"}</p>
      <h2>{detail.display_name || detail.class_type}</h2>
      <code className="breakable">{detail.class_type}</code>
      <dl className="registry-facts">
        <div><dt>Module</dt><dd>{detail.python_module || "Unknown"}</dd></div>
        <div><dt>Fingerprint</dt><dd><code>{detail.schema_fingerprint}</code></dd></div>
        <div><dt>Seen in workflows</dt><dd>{detail.workflow_occurrence_count}</dd></div>
      </dl>
      {detail.description ? <p className="muted registry-description">{detail.description}</p> : null}

      <h3>Semantic mappings</h3>
      <div className="mapping-list">
        {detail.mappings.map((item) => (
          <div key={item.id}>
            <code>{item.locator}</code>
            <span>
              <strong>{titleCase(item.semantic_type)}</strong>
              <small>
                {titleCase(item.role || "no role")} · {titleCase(item.source)} ·{" "}
                {Math.round(item.confidence * 100)}%
              </small>
            </span>
          </div>
        ))}
        {detail.mappings.length === 0 ? <p className="muted">No mappings yet.</p> : null}
      </div>

      <form className="compact-form registry-mapping-form" onSubmit={submit}>
        <h3>Add or correct a mapping</h3>
        <label>
          Value locator
          <input
            list={`node-inputs-${detail.id}`}
            value={locator}
            placeholder="input:model_name or widget:0"
            required
            onChange={(event) => setLocator(event.target.value)}
          />
          <datalist id={`node-inputs-${detail.id}`}>
            {inputNames.map((name) => <option value={`input:${name}`} key={name} />)}
          </datalist>
        </label>
        <div className="registry-form-row">
          <label>
            Meaning
            <select
              value={semanticType}
              onChange={(event) => setSemanticType(event.target.value)}
            >
              <option value="checkpoint_reference">Checkpoint</option>
              <option value="lora_reference">LoRA</option>
              <option value="prompt">Prompt</option>
              <option value="generation_parameter">Parameter</option>
              <option value="ignore">Ignore</option>
            </select>
          </label>
          <label>
            Role (optional)
            <input
              list={semanticType === "prompt" ? "prompt-role-options" : undefined}
              value={role}
              placeholder={
                semanticType === "prompt"
                  ? "Infer automatically, or choose positive/negative"
                  : "high_noise_model"
              }
              onChange={(event) => setRole(event.target.value)}
            />
            {semanticType === "prompt" ? (
              <>
                <datalist id="prompt-role-options">
                  <option value="positive" />
                  <option value="negative" />
                </datalist>
                <small className="field-hint">
                  Leave blank to infer the conditioning branch. Positive prompts are
                  shown first; negative prompts remain available but collapsed.
                </small>
              </>
            ) : null}
          </label>
        </div>
        {mapping.error ? <RegistryError error={mapping.error} fallback="Mapping failed." /> : null}
        <button
          className="secondary-button"
          type="submit"
          disabled={mapping.isPending || !locator.trim()}
        >
          {mapping.isPending ? "Saving and reprocessing…" : "Save mapping"}
        </button>
      </form>

      <details
        className="workflow-disclosure"
        onToggle={(event) => setShowRaw(event.currentTarget.open)}
      >
        <summary>Raw cached schema</summary>
        {showRaw ? <pre className="registry-json">{JSON.stringify(detail.raw_definition, null, 2)}</pre> : null}
      </details>
    </aside>
  );
}

function schemaInputNames(schema: Record<string, unknown>): string[] {
  const names = new Set<string>();
  for (const section of ["required", "optional", "hidden"]) {
    const value = schema[section];
    if (!value || typeof value !== "object" || Array.isArray(value)) continue;
    Object.keys(value).forEach((name) => names.add(name));
  }
  return Array.from(names).sort();
}
