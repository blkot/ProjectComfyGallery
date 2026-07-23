import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useEffect, useMemo, useState } from "react";

import {
  RegistryError,
  RegistryPagination,
  RegistryStatusChip,
  RegistrySyncHistory,
  registryPageSize,
} from "../components/registry-shared";
import {
  apiRequest,
  type ComparisonGroup,
  type LoraSeries,
  type LoraSeriesMember,
  type ModelArtifact,
  type ModelArtifactDetail,
  type ModelArtifactPage,
  type ModelArtifactUpdated,
  type ModelReference,
  type ModelReferenceLinked,
  type ModelReferencePage,
  type RegistrySyncCreated,
  type RegistrySyncRun,
} from "../lib/api";
import { titleCase } from "../lib/format";

type RegistryTab = "artifacts" | "references" | "series" | "groups";

const terminalStatuses = new Set(["succeeded", "partial", "failed", "cancelled"]);

export function ModelRegistryPage() {
  const queryClient = useQueryClient();
  const [baseUrl, setBaseUrl] = useState("");
  const [runScans, setRunScans] = useState(true);
  const [fetchCivitai, setFetchCivitai] = useState(true);
  const [tab, setTab] = useState<RegistryTab>("artifacts");

  const syncRuns = useQuery({
    queryKey: ["registry-sync-runs", "model"],
    queryFn: () =>
      apiRequest<RegistrySyncRun[]>("/api/v1/registry-sync-runs?registry_kind=model"),
    refetchInterval: (query) =>
      query.state.data?.some((run) => !terminalStatuses.has(run.status))
        ? 2_000
        : false,
  });
  const sync = useMutation({
    mutationFn: () =>
      apiRequest<RegistrySyncCreated>("/api/v1/model-registry/sync", {
        method: "POST",
        body: JSON.stringify({
          base_url: baseUrl.trim() || null,
          run_scans: runScans,
          fetch_civitai: fetchCivitai,
        }),
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
      queryClient.invalidateQueries({ queryKey: ["models"] }),
      queryClient.invalidateQueries({ queryKey: ["model-references"] }),
      queryClient.invalidateQueries({ queryKey: ["lora-series"] }),
    ]);
  }, [activeRun, queryClient, syncRuns.data]);

  return (
    <main className="page registry-page">
      <header className="page-header compact-header">
        <div>
          <p className="kicker">Resolvable identity · Phase 3</p>
          <h1>Model registry</h1>
          <p className="muted">
            Reconcile workflow references with LoRA Manager inventory while preserving
            missing and unknown historical models as first-class records.
          </p>
        </div>
        <span className="health-pill" data-state={activeRun ? "wait" : "ok"}>
          <span />
          {activeRun
            ? `${titleCase(activeRun.current_stage ?? "syncing")}…`
            : "Offline cache ready"}
        </span>
      </header>

      {sync.error ? <RegistryError error={sync.error} fallback="Model sync failed." /> : null}

      <section className="panel registry-sync-panel">
        <div>
          <p className="kicker">LoRA Manager + ComfyUI</p>
          <h2>Refresh model inventory</h2>
          <p className="muted">
            The default run asks LoRA Manager to rescan local files and attempt Civitai
            enrichment. Unmatched personal models remain valid local artifacts.
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
          <div className="registry-checks">
            <label>
              <input
                type="checkbox"
                checked={runScans}
                onChange={(event) => setRunScans(event.target.checked)}
              />
              Rescan local models first
            </label>
            <label>
              <input
                type="checkbox"
                checked={fetchCivitai}
                onChange={(event) => setFetchCivitai(event.target.checked)}
              />
              Request Civitai metadata
            </label>
          </div>
          <button
            className="primary-button"
            type="button"
            disabled={sync.isPending || Boolean(activeRun)}
            onClick={() => sync.mutate()}
          >
            {sync.isPending || activeRun ? "Synchronizing…" : "Sync model registry"}
          </button>
        </div>
      </section>

      <RegistrySyncHistory runs={syncRuns.data ?? []} />

      <nav className="registry-tabs section-block" aria-label="Model registry sections">
        <TabButton current={tab} value="artifacts" onSelect={setTab}>
          Model artifacts
        </TabButton>
        <TabButton current={tab} value="references" onSelect={setTab}>
          Workflow references
        </TabButton>
        <TabButton current={tab} value="series" onSelect={setTab}>
          Training series
        </TabButton>
        <TabButton current={tab} value="groups" onSelect={setTab}>
          Comparison groups
        </TabButton>
      </nav>

      {tab === "artifacts" ? <ArtifactsPanel /> : null}
      {tab === "references" ? <ReferencesPanel /> : null}
      {tab === "series" ? <SeriesPanel /> : null}
      {tab === "groups" ? <ComparisonGroupsPanel /> : null}
    </main>
  );
}

function ArtifactsPanel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [artifactType, setArtifactType] = useState("");
  const [availability, setAvailability] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const deferredSearch = useDeferredValue(search);

  const artifacts = useQuery({
    queryKey: ["models", deferredSearch, artifactType, availability, offset],
    queryFn: () => {
      const parameters = new URLSearchParams({
        limit: String(registryPageSize),
        offset: String(offset),
      });
      if (deferredSearch.trim()) parameters.set("search", deferredSearch.trim());
      if (artifactType) parameters.set("artifact_type", artifactType);
      if (availability) parameters.set("availability", availability);
      return apiRequest<ModelArtifactPage>(`/api/v1/models?${parameters.toString()}`);
    },
  });
  const selected = useQuery({
    queryKey: ["model", selectedId],
    queryFn: () => apiRequest<ModelArtifactDetail>(`/api/v1/models/${selectedId}`),
    enabled: Boolean(selectedId),
  });

  return (
    <section className="registry-section">
      <div className="section-heading">
        <div>
          <p className="kicker">Inventory identities</p>
          <h2>Models and adapters</h2>
        </div>
        <span className="document-count">{artifacts.data?.total ?? "—"} artifacts</span>
      </div>
      {artifacts.error ? <RegistryError error={artifacts.error} fallback="Models failed to load." /> : null}
      <div className="registry-toolbar">
        <label className="wide-field">
          Find model
          <input
            type="search"
            value={search}
            placeholder="Name, architecture, lineage, or path"
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Type
          <select
            value={artifactType}
            onChange={(event) => {
              setArtifactType(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Any type</option>
            <option value="checkpoint">Checkpoint</option>
            <option value="lora">LoRA</option>
            <option value="diffusion_model">Diffusion model</option>
            <option value="unet">UNet</option>
          </select>
        </label>
        <label>
          Availability
          <select
            value={availability}
            onChange={(event) => {
              setAvailability(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Any state</option>
            <option value="present">Present</option>
            <option value="missing">Missing</option>
            <option value="unknown">Unknown</option>
          </select>
        </label>
      </div>
      <div className="registry-split">
        <div className="registry-records" aria-busy={artifacts.isFetching}>
          {artifacts.data?.items.map((artifact) => (
            <button
              className="registry-record"
              data-selected={selectedId === artifact.id}
              type="button"
              key={artifact.id}
              onClick={() => setSelectedId(artifact.id)}
            >
              <span>
                <strong>{artifact.display_name}</strong>
                <code>{artifact.file_name || artifact.provider}</code>
              </span>
              <span>
                <small>
                  {[artifact.architecture_family, artifact.lineage]
                    .filter(Boolean)
                    .join(" · ") || "Architecture not classified"}
                </small>
                <span className="registry-chips">
                  <RegistryStatusChip value={artifact.artifact_type} />
                  <RegistryStatusChip value={artifact.availability} />
                  <RegistryStatusChip value={artifact.enrichment_state} />
                </span>
              </span>
            </button>
          ))}
          {artifacts.isPending ? <p className="muted registry-loading">Loading…</p> : null}
          {artifacts.data?.items.length === 0 ? (
            <div className="empty-state">
              <strong>No artifacts match</strong>
              <p>Change the filters or run a model synchronization.</p>
            </div>
          ) : null}
          <RegistryPagination
            offset={offset}
            total={artifacts.data?.total ?? 0}
            onChange={setOffset}
          />
        </div>
        <ArtifactEditor
          key={selectedId ?? "empty"}
          detail={selected.data}
          loading={selected.isPending && Boolean(selectedId)}
          onUpdated={async () => {
            await Promise.all([
              queryClient.invalidateQueries({ queryKey: ["models"] }),
              queryClient.invalidateQueries({ queryKey: ["model", selectedId] }),
              queryClient.invalidateQueries({ queryKey: ["jobs"] }),
            ]);
          }}
        />
      </div>
    </section>
  );
}

function ArtifactEditor({
  detail,
  loading,
  onUpdated,
}: {
  detail: ModelArtifactDetail | undefined;
  loading: boolean;
  onUpdated: () => Promise<void>;
}) {
  if (loading) {
    return <aside className="panel registry-detail"><p className="muted">Loading model…</p></aside>;
  }
  if (!detail) {
    return (
      <aside className="panel registry-detail empty-state">
        <strong>Select a model artifact</strong>
        <p>Its identity, provenance, and analysis labels will appear here.</p>
      </aside>
    );
  }
  return <ArtifactEditorForm detail={detail} onUpdated={onUpdated} />;
}

function ArtifactEditorForm({
  detail,
  onUpdated,
}: {
  detail: ModelArtifactDetail;
  onUpdated: () => Promise<void>;
}) {
  const [fields, setFields] = useState({
    display_name: detail.display_name,
    architecture_family: detail.architecture_family ?? "",
    lineage: detail.lineage ?? "",
    variant: detail.variant ?? "",
    precision: detail.precision ?? "",
    quantization: detail.quantization ?? "",
    availability: detail.availability,
  });
  const [showRaw, setShowRaw] = useState(false);

  const update = useMutation({
    mutationFn: () =>
      apiRequest<ModelArtifactUpdated>(`/api/v1/models/${detail.id}`, {
        method: "PATCH",
        body: JSON.stringify(
          Object.fromEntries(
            Object.entries(fields).map(([key, value]) => [
              key,
              key === "display_name" || key === "availability" ? value : value || null,
            ]),
          ),
        ),
      }),
    onSuccess: onUpdated,
  });

  return (
    <aside className="panel registry-detail">
      <p className="kicker">{titleCase(detail.artifact_type)} · {titleCase(detail.provider)}</p>
      <h2>{detail.display_name}</h2>
      <code className="breakable">{detail.file_path || detail.file_name || detail.id}</code>
      <dl className="registry-facts">
        <div><dt>SHA-256</dt><dd><code>{detail.sha256 || "Unavailable"}</code></dd></div>
        <div><dt>Identity</dt><dd>{titleCase(detail.identity_state)}</dd></div>
        <div><dt>Enrichment</dt><dd>{titleCase(detail.enrichment_state)}</dd></div>
      </dl>
      {detail.provider_url ? (
        <a className="registry-provider-link" href={detail.provider_url} target="_blank" rel="noreferrer">
          Open provider record
        </a>
      ) : null}

      <form
        className="compact-form registry-editor-form"
        onSubmit={(event) => {
          event.preventDefault();
          update.mutate();
        }}
      >
        <h3>Correct analysis labels</h3>
        <label>
          Display name
          <input
            required
            value={fields.display_name}
            onChange={(event) =>
              setFields((current) => ({ ...current, display_name: event.target.value }))
            }
          />
        </label>
        <div className="registry-form-row">
          <label>
            Architecture family
            <input
              value={fields.architecture_family}
              placeholder="Wan 2.2, Krea 2"
              onChange={(event) =>
                setFields((current) => ({
                  ...current,
                  architecture_family: event.target.value,
                }))
              }
            />
          </label>
          <label>
            Lineage
            <input
              value={fields.lineage}
              placeholder="Turbo, Raw, Moody"
              onChange={(event) =>
                setFields((current) => ({ ...current, lineage: event.target.value }))
              }
            />
          </label>
        </div>
        <div className="registry-form-row">
          <label>
            Variant
            <input
              value={fields.variant}
              onChange={(event) =>
                setFields((current) => ({ ...current, variant: event.target.value }))
              }
            />
          </label>
          <label>
            Availability
            <select
              value={fields.availability}
              onChange={(event) =>
                setFields((current) => ({ ...current, availability: event.target.value }))
              }
            >
              <option value="present">Present</option>
              <option value="missing">Missing</option>
              <option value="unknown">Unknown</option>
            </select>
          </label>
        </div>
        <div className="registry-form-row">
          <label>
            Precision
            <input
              value={fields.precision}
              onChange={(event) =>
                setFields((current) => ({ ...current, precision: event.target.value }))
              }
            />
          </label>
          <label>
            Quantization
            <input
              value={fields.quantization}
              onChange={(event) =>
                setFields((current) => ({ ...current, quantization: event.target.value }))
              }
            />
          </label>
        </div>
        {update.error ? <RegistryError error={update.error} fallback="Model update failed." /> : null}
        <button className="secondary-button" type="submit" disabled={update.isPending}>
          {update.isPending ? "Saving and resolving…" : "Save corrections"}
        </button>
      </form>

      <details
        className="workflow-disclosure"
        onToggle={(event) => setShowRaw(event.currentTarget.open)}
      >
        <summary>Raw inventory and provider metadata</summary>
        {showRaw ? (
          <pre className="registry-json">
            {JSON.stringify(
              { inventory: detail.raw_inventory, provider: detail.raw_provider_metadata },
              null,
              2,
            )}
          </pre>
        ) : null}
      </details>
    </aside>
  );
}

function ReferencesPanel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [resolution, setResolution] = useState("");
  const [referenceType, setReferenceType] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<ModelReference | null>(null);
  const deferredSearch = useDeferredValue(search);

  const references = useQuery({
    queryKey: ["model-references", deferredSearch, resolution, referenceType, offset],
    queryFn: () => {
      const parameters = new URLSearchParams({
        limit: String(registryPageSize),
        offset: String(offset),
      });
      if (deferredSearch.trim()) parameters.set("search", deferredSearch.trim());
      if (resolution) parameters.set("resolution_state", resolution);
      if (referenceType) parameters.set("reference_type", referenceType);
      return apiRequest<ModelReferencePage>(
        `/api/v1/model-references?${parameters.toString()}`,
      );
    },
  });
  const artifacts = useQuery({
    queryKey: ["models", "reference-link-options"],
    queryFn: () => apiRequest<ModelArtifactPage>("/api/v1/models?limit=500"),
    enabled: Boolean(selected),
  });

  return (
    <section className="registry-section">
      <div className="section-heading">
        <div>
          <p className="kicker">Workflow vocabulary</p>
          <h2>Embedded model references</h2>
        </div>
        <span className="document-count">{references.data?.total ?? "—"} references</span>
      </div>
      <div className="registry-toolbar">
        <label className="wide-field">
          Find reference
          <input
            type="search"
            value={search}
            placeholder="Exact text embedded in workflows"
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
          />
        </label>
        <label>
          Resolution
          <select
            value={resolution}
            onChange={(event) => {
              setResolution(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Any state</option>
            <option value="resolved">Resolved</option>
            <option value="ambiguous">Ambiguous</option>
            <option value="unresolved">Unresolved</option>
            <option value="historical">Historical</option>
          </select>
        </label>
        <label>
          Type
          <select
            value={referenceType}
            onChange={(event) => {
              setReferenceType(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">Checkpoint + LoRA</option>
            <option value="checkpoint">Checkpoint</option>
            <option value="lora">LoRA</option>
          </select>
        </label>
      </div>
      <div className="registry-split">
        <div className="registry-records">
          {references.data?.items.map((reference) => (
            <button
              className="registry-record"
              data-selected={selected?.id === reference.id}
              type="button"
              key={reference.id}
              onClick={() => setSelected(reference)}
            >
              <span>
                <strong>{reference.raw_value}</strong>
                <code>{reference.normalized_value}</code>
              </span>
              <span>
                <small>
                  {reference.match_method
                    ? `${titleCase(reference.match_method)} · ${Math.round((reference.confidence ?? 0) * 100)}%`
                    : "No identity match"}
                </small>
                <span className="registry-chips">
                  <RegistryStatusChip value={reference.reference_type} />
                  <RegistryStatusChip value={reference.resolution_state} />
                  <em>{reference.occurrence_count} uses</em>
                </span>
              </span>
            </button>
          ))}
          {references.data?.items.length === 0 ? (
            <div className="empty-state">
              <strong>No workflow references match</strong>
              <p>References appear after media workflow extraction.</p>
            </div>
          ) : null}
          <RegistryPagination
            offset={offset}
            total={references.data?.total ?? 0}
            onChange={setOffset}
          />
        </div>
        <ReferenceLinker
          key={selected?.id ?? "empty"}
          reference={selected}
          artifacts={artifacts.data?.items ?? []}
          onLinked={async () => {
            setSelected(null);
            await Promise.all([
              queryClient.invalidateQueries({ queryKey: ["model-references"] }),
              queryClient.invalidateQueries({ queryKey: ["lora-series"] }),
              queryClient.invalidateQueries({ queryKey: ["jobs"] }),
            ]);
          }}
        />
      </div>
    </section>
  );
}

function ReferenceLinker({
  reference,
  artifacts,
  onLinked,
}: {
  reference: ModelReference | null;
  artifacts: ModelArtifact[];
  onLinked: () => Promise<void>;
}) {
  const [artifactId, setArtifactId] = useState(reference?.artifact_id ?? "");
  const compatible = useMemo(
    () =>
      artifacts.filter(
        (artifact) =>
          artifact.artifact_type === reference?.reference_type ||
          (reference?.reference_type === "checkpoint" &&
            ["diffusion_model", "unet"].includes(artifact.artifact_type)),
      ),
    [artifacts, reference?.reference_type],
  );
  const link = useMutation({
    mutationFn: () =>
      apiRequest<ModelReferenceLinked>(
        `/api/v1/model-references/${reference?.id}/link`,
        {
          method: "POST",
          body: JSON.stringify({ artifact_id: artifactId || null }),
        },
      ),
    onSuccess: onLinked,
  });

  if (!reference) {
    return (
      <aside className="panel registry-detail empty-state">
        <strong>Select a workflow reference</strong>
        <p>Link an unresolved or ambiguous name to a known artifact.</p>
      </aside>
    );
  }
  return (
    <aside className="panel registry-detail">
      <p className="kicker">{titleCase(reference.reference_type)} reference</p>
      <h2 className="breakable">{reference.raw_value}</h2>
      <dl className="registry-facts">
        <div><dt>Resolution</dt><dd>{titleCase(reference.resolution_state)}</dd></div>
        <div><dt>Availability</dt><dd>{titleCase(reference.availability)}</dd></div>
        <div><dt>Occurrences</dt><dd>{reference.occurrence_count}</dd></div>
      </dl>
      <form
        className="compact-form registry-editor-form"
        onSubmit={(event) => {
          event.preventDefault();
          link.mutate();
        }}
      >
        <h3>Manual identity link</h3>
        <label>
          Model artifact
          <select value={artifactId} onChange={(event) => setArtifactId(event.target.value)}>
            <option value="">Keep as historical / unlinked</option>
            {compatible.map((artifact) => (
              <option value={artifact.id} key={artifact.id}>
                {artifact.display_name}
              </option>
            ))}
          </select>
        </label>
        {link.error ? <RegistryError error={link.error} fallback="Linking failed." /> : null}
        <button className="secondary-button" type="submit" disabled={link.isPending}>
          {link.isPending ? "Linking and resolving…" : "Save identity link"}
        </button>
      </form>
    </aside>
  );
}

function SeriesPanel() {
  const queryClient = useQueryClient();
  const series = useQuery({
    queryKey: ["lora-series"],
    queryFn: () => apiRequest<LoraSeries[]>("/api/v1/lora-series"),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = series.data?.find((item) => item.id === selectedId);

  return (
    <section className="registry-section">
      <div className="section-heading">
        <div>
          <p className="kicker">Personal training runs</p>
          <h2>LoRA step series</h2>
        </div>
        <span className="document-count">{series.data?.length ?? "—"} series</span>
      </div>
      <p className="muted registry-section-intro">
        Only the exact trailing numeric suffix is interpreted: for example,
        <code> Krea2_guzong_lora_v2_000003500</code> becomes opaque series
        <code> Krea2_guzong_lora_v2</code> at step 3500.
      </p>
      <div className="registry-split">
        <div className="registry-records">
          {series.data?.map((item) => (
            <button
              className="registry-record"
              data-selected={selectedId === item.id}
              type="button"
              key={item.id}
              onClick={() => setSelectedId(item.id)}
            >
              <span>
                <strong>{item.display_name}</strong>
                <code>{item.opaque_name}</code>
              </span>
              <span>
                <small>{item.members.length} checkpoints</small>
                <span className="registry-chips">
                  <RegistryStatusChip value={item.source} />
                  <RegistryStatusChip value={item.correction_state} />
                </span>
              </span>
            </button>
          ))}
          {series.data?.length === 0 ? (
            <div className="empty-state">
              <strong>No LoRA training series detected</strong>
              <p>Series appear after workflow references with exact step suffixes are resolved.</p>
            </div>
          ) : null}
        </div>
        <SeriesEditor
          key={selected?.id ?? "empty"}
          series={selected}
          allSeries={series.data ?? []}
          onUpdated={async () => {
            await queryClient.invalidateQueries({ queryKey: ["lora-series"] });
          }}
        />
      </div>
    </section>
  );
}

function SeriesEditor({
  series,
  allSeries,
  onUpdated,
}: {
  series: LoraSeries | undefined;
  allSeries: LoraSeries[];
  onUpdated: () => Promise<void>;
}) {
  const [displayName, setDisplayName] = useState(series?.display_name ?? "");
  const [mergeSourceId, setMergeSourceId] = useState("");
  const [splitMemberIds, setSplitMemberIds] = useState<Set<string>>(new Set());
  const [splitOpaqueName, setSplitOpaqueName] = useState("");
  const [splitDisplayName, setSplitDisplayName] = useState("");
  const rename = useMutation({
    mutationFn: () =>
      apiRequest<LoraSeries>(`/api/v1/lora-series/${series?.id}`, {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
    }),
    onSuccess: onUpdated,
  });
  const merge = useMutation({
    mutationFn: () =>
      apiRequest<LoraSeries>(`/api/v1/lora-series/${series?.id}/merge`, {
        method: "POST",
        body: JSON.stringify({ source_series_ids: [mergeSourceId] }),
      }),
    onSuccess: async () => {
      setMergeSourceId("");
      await onUpdated();
    },
  });
  const split = useMutation({
    mutationFn: () =>
      apiRequest<LoraSeries>(`/api/v1/lora-series/${series?.id}/split`, {
        method: "POST",
        body: JSON.stringify({
          opaque_name: splitOpaqueName,
          display_name: splitDisplayName,
          member_ids: [...splitMemberIds],
        }),
      }),
    onSuccess: async () => {
      setSplitMemberIds(new Set());
      setSplitOpaqueName("");
      setSplitDisplayName("");
      await onUpdated();
    },
  });

  if (!series) {
    return (
      <aside className="panel registry-detail empty-state">
        <strong>Select a training series</strong>
        <p>Review the opaque name and correct individual step values.</p>
      </aside>
    );
  }
  return (
    <aside className="panel registry-detail">
      <p className="kicker">Opaque training identity</p>
      <h2>{series.display_name}</h2>
      <code className="breakable">{series.opaque_name}</code>
      <form
        className="compact-form registry-editor-form"
        onSubmit={(event) => {
          event.preventDefault();
          rename.mutate();
        }}
      >
        <label>
          Display name
          <input
            required
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
          />
        </label>
        <button className="secondary-button" type="submit" disabled={rename.isPending}>
          Save series name
        </button>
      </form>
      <form
        className="compact-form series-structure-form"
        onSubmit={(event) => {
          event.preventDefault();
          merge.mutate();
        }}
      >
        <label>
          Merge another series into this one
          <select
            required
            value={mergeSourceId}
            onChange={(event) => setMergeSourceId(event.target.value)}
          >
            <option value="">Select a source series</option>
            {allSeries
              .filter((item) => item.id !== series.id)
              .map((item) => (
                <option value={item.id} key={item.id}>
                  {item.display_name} · {item.members.length} members
                </option>
              ))}
          </select>
        </label>
        <button
          className="secondary-button"
          type="submit"
          disabled={merge.isPending || !mergeSourceId}
        >
          Merge into this series
        </button>
      </form>
      {merge.error ? <RegistryError error={merge.error} fallback="Series merge failed." /> : null}
      <h3 className="registry-subheading">Detected checkpoints</h3>
      <p className="muted registry-section-intro">
        Select checkpoints below when a filename pattern grouped separate training runs
        together.
      </p>
      <div className="series-members">
        {series.members
          .slice()
          .sort((left, right) => left.training_step - right.training_step)
          .map((member) => (
            <SeriesMemberEditor
              member={member}
              selected={splitMemberIds.has(member.id)}
              onSelected={(selected) => {
                setSplitMemberIds((current) => {
                  const next = new Set(current);
                  if (selected) next.add(member.id);
                  else next.delete(member.id);
                  return next;
                });
              }}
              onUpdated={onUpdated}
              key={`${member.id}-${member.training_step}`}
            />
          ))}
      </div>
      <form
        className="compact-form series-structure-form"
        onSubmit={(event) => {
          event.preventDefault();
          split.mutate();
        }}
      >
        <div className="registry-form-row">
          <label>
            New opaque series name
            <input
              required
              value={splitOpaqueName}
              onChange={(event) => setSplitOpaqueName(event.target.value)}
              placeholder="My_character_lora_v3"
            />
          </label>
          <label>
            New display name
            <input
              required
              value={splitDisplayName}
              onChange={(event) => setSplitDisplayName(event.target.value)}
              placeholder="Character LoRA v3"
            />
          </label>
        </div>
        <button
          className="secondary-button"
          type="submit"
          disabled={
            split.isPending ||
            splitMemberIds.size === 0 ||
            !splitOpaqueName.trim() ||
            !splitDisplayName.trim()
          }
        >
          Split {splitMemberIds.size || "selected"} into a new series
        </button>
      </form>
      {split.error ? <RegistryError error={split.error} fallback="Series split failed." /> : null}
    </aside>
  );
}

function SeriesMemberEditor({
  member,
  selected,
  onSelected,
  onUpdated,
}: {
  member: LoraSeriesMember;
  selected: boolean;
  onSelected: (selected: boolean) => void;
  onUpdated: () => Promise<void>;
}) {
  const [step, setStep] = useState(String(member.training_step));
  const update = useMutation({
    mutationFn: () =>
      apiRequest<LoraSeriesMember>(`/api/v1/lora-series-members/${member.id}`, {
        method: "PATCH",
        body: JSON.stringify({ training_step: Number(step) }),
      }),
    onSuccess: onUpdated,
  });
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        update.mutate();
      }}
    >
      <span>
        <label className="series-member-selector">
          <input
            type="checkbox"
            checked={selected}
            onChange={(event) => onSelected(event.target.checked)}
          />
          <span>
            <code>{member.model_reference_id.slice(0, 8)}</code>
            <small>{titleCase(member.correction_state)}</small>
          </span>
        </label>
      </span>
      <label>
        <span className="sr-only">Training step</span>
        <input
          type="number"
          min="0"
          step="1"
          value={step}
          onChange={(event) => setStep(event.target.value)}
        />
      </label>
      <button
        className="text-button inline-text-button"
        type="submit"
        disabled={update.isPending || Number(step) === member.training_step}
      >
        Save
      </button>
    </form>
  );
}

function ComparisonGroupsPanel() {
  const queryClient = useQueryClient();
  const groups = useQuery({
    queryKey: ["comparison-groups"],
    queryFn: () => apiRequest<ComparisonGroup[]>("/api/v1/comparison-groups"),
  });
  const artifacts = useQuery({
    queryKey: ["models", "comparison-options"],
    queryFn: () => apiRequest<ModelArtifactPage>("/api/v1/models?limit=500"),
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = groups.data?.find((group) => group.id === selectedId);

  return (
    <section className="registry-section">
      <div className="section-heading">
        <div>
          <p className="kicker">Analysis boundary</p>
          <h2>Comparison groups</h2>
        </div>
        <button className="secondary-button" type="button" onClick={() => setSelectedId("new")}>
          New group
        </button>
      </div>
      <p className="muted registry-section-intro">
        Groups express your decision about which checkpoint artifacts may compete.
        They do not declare a winner and do not force unrelated architectures together.
      </p>
      <div className="registry-split">
        <div className="registry-records">
          {groups.data?.map((group) => (
            <button
              className="registry-record"
              data-selected={selectedId === group.id}
              type="button"
              key={group.id}
              onClick={() => setSelectedId(group.id)}
            >
              <span>
                <strong>{group.name}</strong>
                <small>{group.description || "No description"}</small>
              </span>
              <span>
                <small>{group.members.length} model artifacts</small>
                <span className="registry-chips">
                  <RegistryStatusChip value={group.enabled ? "enabled" : "disabled"} />
                </span>
              </span>
            </button>
          ))}
          {groups.data?.length === 0 ? (
            <div className="empty-state">
              <strong>No comparison groups</strong>
              <p>Create one when you know which checkpoint lineages belong in one analysis pool.</p>
            </div>
          ) : null}
        </div>
        <ComparisonGroupEditor
          key={selectedId ?? "empty"}
          group={selectedId === "new" ? null : selected}
          creating={selectedId === "new"}
          artifacts={artifacts.data?.items ?? []}
          onSaved={async (group) => {
            setSelectedId(group.id);
            await queryClient.invalidateQueries({ queryKey: ["comparison-groups"] });
          }}
        />
      </div>
    </section>
  );
}

function ComparisonGroupEditor({
  group,
  creating,
  artifacts,
  onSaved,
}: {
  group: ComparisonGroup | null | undefined;
  creating: boolean;
  artifacts: ModelArtifact[];
  onSaved: (group: ComparisonGroup) => Promise<void>;
}) {
  const [name, setName] = useState(group?.name ?? "");
  const [description, setDescription] = useState(group?.description ?? "");
  const [enabled, setEnabled] = useState(group?.enabled ?? true);
  const [artifactIds, setArtifactIds] = useState<string[]>(
    group?.members.map((member) => member.artifact_id) ?? [],
  );
  const [candidateId, setCandidateId] = useState("");

  const save = useMutation({
    mutationFn: () =>
      apiRequest<ComparisonGroup>(
        creating ? "/api/v1/comparison-groups" : `/api/v1/comparison-groups/${group?.id}`,
        {
          method: creating ? "POST" : "PATCH",
          body: JSON.stringify({
            name,
            description: description.trim() || null,
            enabled,
            artifact_ids: artifactIds,
          }),
        },
      ),
    onSuccess: onSaved,
  });

  if (!creating && !group) {
    return (
      <aside className="panel registry-detail empty-state">
        <strong>Select or create a comparison group</strong>
        <p>Membership is an explicit filter for future experiments.</p>
      </aside>
    );
  }

  const available = artifacts.filter(
    (artifact) =>
      !artifactIds.includes(artifact.id) &&
      artifact.artifact_type !== "lora",
  );
  const selectedArtifacts = artifactIds
    .map((id) => artifacts.find((artifact) => artifact.id === id))
    .filter((artifact): artifact is ModelArtifact => Boolean(artifact));

  return (
    <aside className="panel registry-detail">
      <p className="kicker">{creating ? "New analysis boundary" : "Edit analysis boundary"}</p>
      <h2>{creating ? "Comparison group" : group?.name}</h2>
      <form
        className="compact-form registry-editor-form"
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
      >
        <label>
          Name
          <input required value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label>
          Description
          <textarea
            value={description}
            placeholder="Why these model lineages can be compared"
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Enabled for experiment filters
        </label>
        <div className="group-member-picker">
          <label>
            Add model artifact
            <select value={candidateId} onChange={(event) => setCandidateId(event.target.value)}>
              <option value="">Choose a checkpoint…</option>
              {available.map((artifact) => (
                <option value={artifact.id} key={artifact.id}>
                  {artifact.display_name}
                </option>
              ))}
            </select>
          </label>
          <button
            className="secondary-button"
            type="button"
            disabled={!candidateId}
            onClick={() => {
              setArtifactIds((current) => [...current, candidateId]);
              setCandidateId("");
            }}
          >
            Add
          </button>
        </div>
        <div className="group-members">
          {selectedArtifacts.map((artifact) => (
            <div key={artifact.id}>
              <span>
                <strong>{artifact.display_name}</strong>
                <small>
                  {[artifact.architecture_family, artifact.lineage]
                    .filter(Boolean)
                    .join(" · ") || titleCase(artifact.artifact_type)}
                </small>
              </span>
              <button
                className="text-button inline-text-button"
                type="button"
                onClick={() =>
                  setArtifactIds((current) =>
                    current.filter((artifactId) => artifactId !== artifact.id),
                  )
                }
              >
                Remove
              </button>
            </div>
          ))}
          {selectedArtifacts.length === 0 ? <p className="muted">No members selected.</p> : null}
        </div>
        {save.error ? <RegistryError error={save.error} fallback="Group could not be saved." /> : null}
        <button className="primary-button" type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : creating ? "Create group" : "Save group"}
        </button>
      </form>
    </aside>
  );
}

function TabButton({
  children,
  current,
  value,
  onSelect,
}: {
  children: React.ReactNode;
  current: RegistryTab;
  value: RegistryTab;
  onSelect: (value: RegistryTab) => void;
}) {
  return (
    <button
      type="button"
      aria-current={current === value ? "page" : undefined}
      onClick={() => onSelect(value)}
    >
      {children}
    </button>
  );
}
