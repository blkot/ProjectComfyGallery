import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  ApiClientError,
  apiRequest,
  type Job,
  type SemanticObservation,
  type WorkflowDetail,
  type WorkflowModelUsage,
  type WorkflowNode,
  type WorkflowRawEvidence,
} from "../lib/api";
import { copyText } from "../lib/clipboard";
import { formatDate, titleCase } from "../lib/format";
import { orderPrompts } from "../lib/prompts";

type WorkflowInspectorProps = {
  mediaId: string;
};

type PromptCopyState = {
  index: number;
  status: "copying" | "copied" | "failed";
};

const terminalJobStatuses = new Set(["succeeded", "failed", "cancelled"]);

export function WorkflowInspector({ mediaId }: WorkflowInspectorProps) {
  const queryClient = useQueryClient();
  const [representation, setRepresentation] = useState("");
  const [nodeSearch, setNodeSearch] = useState("");
  const [showGraph, setShowGraph] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const workflow = useQuery({
    queryKey: ["media-workflow", mediaId],
    queryFn: () =>
      apiRequest<WorkflowDetail>(
        `/api/v1/media/${mediaId}/workflow?node_limit=1000&edge_limit=3000`,
      ),
  });
  const rawEvidence = useQuery({
    queryKey: ["media-workflow-raw", mediaId],
    queryFn: () =>
      apiRequest<WorkflowRawEvidence>(`/api/v1/media/${mediaId}/workflow/raw`),
    enabled: showRaw && Boolean(workflow.data?.snapshot),
  });
  const extractionJob = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiRequest<Job>(`/api/v1/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalJobStatuses.has(status) ? false : 2_000;
    },
  });
  const reprocess = useMutation({
    mutationFn: () =>
      apiRequest<Job>(`/api/v1/media/${mediaId}/workflow/reprocess`, {
        method: "POST",
      }),
    onSuccess: async (job) => {
      setJobId(job.id);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const jobStatus = extractionJob.data?.status;
  useEffect(() => {
    if (!jobStatus || !terminalJobStatuses.has(jobStatus)) return;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["media-workflow", mediaId] }),
      queryClient.invalidateQueries({ queryKey: ["media-detail", mediaId] }),
      queryClient.invalidateQueries({ queryKey: ["media"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    ]);
  }, [jobStatus, mediaId, queryClient]);

  const filteredNodes = useMemo(() => {
    const query = nodeSearch.trim().toLocaleLowerCase();
    return (workflow.data?.nodes ?? []).filter((node) => {
      if (representation && node.representation !== representation) return false;
      if (!query) return true;
      return (
        node.class_type.toLocaleLowerCase().includes(query) ||
        node.original_node_id.toLocaleLowerCase().includes(query) ||
        node.title?.toLocaleLowerCase().includes(query)
      );
    });
  }, [nodeSearch, representation, workflow.data?.nodes]);

  if (workflow.isPending) {
    return (
      <section className="panel workflow-panel">
        <p className="muted">Reading workflow evidence…</p>
      </section>
    );
  }
  if (workflow.isError || !workflow.data) {
    return (
      <section className="panel workflow-panel">
        <p className="notice error-notice">Workflow evidence could not be loaded.</p>
      </section>
    );
  }

  const data = workflow.data;
  const snapshot = data.snapshot;
  const jobRunning = Boolean(jobStatus && !terminalJobStatuses.has(jobStatus));
  const mutationError = reprocess.error;

  return (
    <section className="workflow-section workflow-inspector">
      <header className="workflow-heading">
        <div>
          <p className="kicker">Embedded ground truth</p>
          <h2>ComfyUI workflow</h2>
        </div>
        <div className="workflow-actions">
          <span className="status-chip" data-status={data.status}>
            {titleCase(data.status)}
          </span>
          <button
            className="secondary-button"
            type="button"
            disabled={reprocess.isPending || jobRunning}
            onClick={() => reprocess.mutate()}
          >
            {reprocess.isPending || jobRunning ? "Extracting…" : "Reprocess"}
          </button>
        </div>
      </header>

      {mutationError ? (
        <p className="notice error-notice" role="alert">
          {mutationError instanceof ApiClientError
            ? mutationError.message
            : "Workflow extraction could not be queued."}
        </p>
      ) : null}
      {jobStatus === "failed" ? (
        <p className="notice error-notice">
          Reprocessing failed. The previous evidence and extraction remain unchanged.
        </p>
      ) : null}

      {!snapshot ? (
        <article className="empty-state large-empty">
          <strong>Workflow evidence has not been extracted</strong>
          <p>Use Reprocess to read the immutable original in the background.</p>
        </article>
      ) : (
        <>
          <PromptPanel observations={data.observations} />
          <ModelUsagePanel
            usages={data.model_usages}
            observations={data.observations}
          />
          <GenerationParameters observations={data.observations} />

          <details className="workflow-inspector-disclosure">
            <summary>
              <span>
                <strong>Workflow diagnostics</strong>
                <small>
                  Parser, evidence carrier, and supplemental observations
                </small>
              </span>
              <span>{data.observations.length} observations</span>
            </summary>
            <div className="workflow-inspector-disclosure-body">
              <EvidenceSummary data={data} />
              <ObservationPanel observations={data.observations} />
            </div>
          </details>

          <details
            className="workflow-inspector-disclosure"
            onToggle={(event) => setShowGraph(event.currentTarget.open)}
          >
            <summary>
              <span>
                <strong>Node graph</strong>
                <small>Inspect normalized nodes and connections</small>
              </span>
              <span>
                {snapshot.api_node_count + snapshot.visual_node_count} nodes
              </span>
            </summary>
            {showGraph ? (
              <article className="workflow-graph-panel">
                <div className="workflow-toolbar">
                  <label>
                    Representation
                    <select
                      value={representation}
                      onChange={(event) => setRepresentation(event.target.value)}
                    >
                      <option value="">Both graphs</option>
                      <option value="api_prompt">API prompt</option>
                      <option value="visual_workflow">Visual workflow</option>
                    </select>
                  </label>
                  <label>
                    Find node
                    <input
                      type="search"
                      value={nodeSearch}
                      placeholder="Class, title, or node ID"
                      onChange={(event) => setNodeSearch(event.target.value)}
                    />
                  </label>
                </div>

                {data.nodes_truncated ? (
                  <p className="notice">
                    This graph exceeds the current inspection page. The database
                    retains all nodes.
                  </p>
                ) : null}
                <div className="workflow-node-list">
                  {filteredNodes.map((node) => (
                    <WorkflowNodeRow node={node} key={node.id} />
                  ))}
                  {filteredNodes.length === 0 ? (
                    <p className="muted">No graph nodes match this filter.</p>
                  ) : null}
                </div>
                <EdgeList
                  edges={data.edges}
                  representation={representation}
                  truncated={data.edges_truncated}
                />
              </article>
            ) : null}
          </details>

          <details className="workflow-inspector-disclosure">
            <summary>
              <span>
                <strong>Raw embedded evidence</strong>
                <small>Immutable decoded workflow and prompt payloads</small>
              </span>
              <span>Load on demand</span>
            </summary>
            <article className="workflow-raw-panel">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setShowRaw((visible) => !visible)}
              >
                {showRaw ? "Hide raw evidence" : "Load raw evidence"}
              </button>
              {showRaw && rawEvidence.isPending ? (
                <p className="muted">Loading preserved payloads…</p>
              ) : null}
              {showRaw && rawEvidence.isError ? (
                <p className="notice error-notice">
                  Raw evidence could not be loaded.
                </p>
              ) : null}
              {showRaw && rawEvidence.data ? (
                <RawEvidence evidence={rawEvidence.data} />
              ) : null}
            </article>
          </details>

          <details className="workflow-inspector-disclosure">
            <summary>
              <span>
                <strong>Extraction history</strong>
                <small>Versioned parser runs</small>
              </span>
              <span>{data.runs.length} runs</span>
            </summary>
            <div className="history-list workflow-run-list">
              {data.runs.map((run) => (
                <div className="history-row" key={run.id}>
                  <span>
                    <strong>
                      {titleCase(run.status)}
                      {run.is_current ? " · current" : ""}
                    </strong>
                    <small>
                      {run.extractor_name} {run.extractor_version} ·{" "}
                      {formatDate(run.started_at)}
                    </small>
                  </span>
                  <span className="history-counts">
                    {run.observation_count} observations
                  </span>
                </div>
              ))}
            </div>
          </details>
        </>
      )}
    </section>
  );
}

function EvidenceSummary({ data }: { data: WorkflowDetail }) {
  const snapshot = data.snapshot;
  if (!snapshot) return null;
  return (
    <div className="workflow-metric-grid">
      <article>
        <span>API prompt</span>
        <strong>{titleCase(snapshot.api_prompt_status)}</strong>
        <small>{snapshot.api_node_count} nodes</small>
      </article>
      <article>
        <span>Visual workflow</span>
        <strong>{titleCase(snapshot.visual_workflow_status)}</strong>
        <small>{snapshot.visual_node_count} nodes</small>
      </article>
      <article>
        <span>Reader</span>
        <strong>{snapshot.reader_version}</strong>
        <small>{titleCase(snapshot.source_carrier)}</small>
      </article>
      <article>
        <span>Evidence SHA-256</span>
        <code title={snapshot.evidence_sha256}>{snapshot.evidence_sha256}</code>
        <small>Decoded embedded metadata</small>
      </article>
    </div>
  );
}

function ObservationPanel({
  observations,
}: {
  observations: SemanticObservation[];
}) {
  const supplemental = observations.filter(
    (observation) =>
      ![
        "checkpoint_reference",
        "generation_parameter",
        "lora_reference",
        "prompt",
      ].includes(observation.observation_type),
  );
  if (!supplemental.length) return null;
  return (
    <article className="workflow-observation-panel">
      <div className="section-heading">
        <div>
          <p className="kicker">Additional evidence</p>
          <h3>Supplemental observations</h3>
        </div>
        <span className="document-count">{supplemental.length}</span>
      </div>
      <div className="observation-list">
        {supplemental.map((observation) => (
          <div
            className="observation-row"
            data-type={observation.observation_type}
            key={observation.id}
          >
            <span>
              <strong>{titleCase(observation.observation_type)}</strong>
              <small>
                {titleCase(observation.role ?? "unclassified")} ·{" "}
                {Math.round(observation.confidence * 100)}% confidence ·{" "}
                {titleCase(observation.correction_state)}
              </small>
            </span>
            <code>{displayValue(observation.value)}</code>
          </div>
        ))}
      </div>
    </article>
  );
}

function ModelUsagePanel({
  usages,
  observations,
}: {
  usages: WorkflowModelUsage[];
  observations: SemanticObservation[];
}) {
  const checkpointUsages = usages.filter(
    (usage) => usage.observation_type === "checkpoint_reference",
  );
  const loraUsages = usages.filter(
    (usage) => usage.observation_type === "lora_reference",
  );
  const checkpointFallback = observations.filter(
    (observation) => observation.observation_type === "checkpoint_reference",
  );
  const loraFallback = observations.filter(
    (observation) => observation.observation_type === "lora_reference",
  );
  return (
    <article className="workflow-priority-card model-evidence-card">
      <div className="section-heading">
        <div>
          <p className="kicker">Primary recipe</p>
          <h2>Checkpoints &amp; LoRAs</h2>
        </div>
        <span className="document-count">
          {usages.length || checkpointFallback.length + loraFallback.length} uses
        </span>
      </div>
      <ModelUsageGroup
        title="Checkpoints"
        emptyMessage="No checkpoint reference was extracted."
        usages={checkpointUsages}
        fallback={checkpointFallback}
      />
      <ModelUsageGroup
        title="LoRAs"
        emptyMessage="No LoRA reference was extracted."
        usages={loraUsages}
        fallback={loraFallback}
      />
    </article>
  );
}

function ModelUsageGroup({
  title,
  emptyMessage,
  usages,
  fallback,
}: {
  title: string;
  emptyMessage: string;
  usages: WorkflowModelUsage[];
  fallback: SemanticObservation[];
}) {
  return (
    <section className="model-evidence-group">
      <header>
        <h3>{title}</h3>
        <span>{usages.length || fallback.length}</span>
      </header>
      {usages.map((usage) => (
        <div className="model-evidence-row" key={usage.id}>
          <strong>{usage.artifact_display_name || usage.raw_reference}</strong>
          <small>
            {titleCase(usage.slot)} · {titleCase(usage.pipeline_pattern)}
          </small>
          <span>
            {usage.architecture_family || "Architecture unknown"}
            {usage.lineage ? ` · ${usage.lineage}` : ""}
          </span>
          {usage.artifact_display_name ? <code>{usage.raw_reference}</code> : null}
        </div>
      ))}
      {usages.length === 0
        ? fallback.map((observation) => (
            <div className="model-evidence-row" key={observation.id}>
              <strong>{displayValue(observation.value)}</strong>
              <small>
                {titleCase(observation.role ?? "unclassified")} · unresolved registry
                usage
              </small>
            </div>
          ))
        : null}
      {usages.length === 0 && fallback.length === 0 ? (
        <p className="muted">{emptyMessage}</p>
      ) : null}
    </section>
  );
}

function PromptPanel({
  observations,
}: {
  observations: SemanticObservation[];
}) {
  const [copyState, setCopyState] = useState<PromptCopyState | null>(null);
  const prompts = orderPrompts(
    observations.filter(
      (observation) => observation.observation_type === "prompt",
    ),
  );

  async function copyPrompt(index: number, text: string) {
    setCopyState({ index, status: "copying" });
    try {
      await copyText(text);
      setCopyState({ index, status: "copied" });
    } catch {
      setCopyState({ index, status: "failed" });
    }
  }

  return (
    <article className="workflow-priority-card prompt-evidence-card">
      <div className="section-heading">
        <div>
          <p className="kicker">Exact embedded text</p>
          <h2>Prompt</h2>
        </div>
        <span className="document-count">{prompts.length}</span>
      </div>
      {prompts.map((prompt, index) => {
        const label = titleCase(prompt.role ?? `Prompt ${index + 1}`);
        const text = displayValue(prompt.value);
        const status = copyState?.index === index ? copyState.status : null;
        return (
          <details
            className="prompt-evidence"
            data-role={prompt.role ?? "unclassified"}
            open={index === 0}
            key={prompt.id}
          >
            <summary>{label}</summary>
            <div className="workflow-prompt-content">
              <pre className="workflow-prompt">{text}</pre>
              <button
                aria-label={status === "copied" ? `${label} copied` : `Copy ${label}`}
                aria-live="polite"
                className="text-button prompt-copy-button"
                type="button"
                disabled={status === "copying"}
                onClick={() => void copyPrompt(index, text)}
              >
                {status === "copying"
                  ? "Copying…"
                  : status === "copied"
                    ? "Copied"
                    : status === "failed"
                      ? "Copy failed"
                      : "Copy prompt"}
              </button>
            </div>
          </details>
        );
      })}
      {prompts.length === 0 ? (
        <p className="muted">No prompt was extracted for this media.</p>
      ) : null}
    </article>
  );
}

function GenerationParameters({
  observations,
}: {
  observations: SemanticObservation[];
}) {
  const parameters = observations.filter(
    (observation) => observation.observation_type === "generation_parameter",
  );
  if (!parameters.length) return null;
  return (
    <details className="workflow-inspector-disclosure parameter-disclosure">
      <summary>
        <span>
          <strong>Generation parameters</strong>
          <small>Sampler and recipe values</small>
        </span>
        <span>{parameters.length}</span>
      </summary>
      <dl className="parameter-grid">
        {parameters.map((parameter) => (
          <div key={parameter.id}>
            <dt>{titleCase(parameter.role ?? "parameter")}</dt>
            <dd>{displayValue(parameter.value)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

function WorkflowNodeRow({ node }: { node: WorkflowNode }) {
  const [open, setOpen] = useState(false);
  return (
    <details
      className="workflow-node-row"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span className="node-representation">
          {node.representation === "api_prompt" ? "API" : "VIS"}
        </span>
        <strong>{node.title || node.class_type}</strong>
        {node.title ? <small>{node.class_type}</small> : null}
        <span
          className="status-chip node-match-chip"
          data-status={node.definition_match_state}
          title={
            node.definition_confidence === null
              ? "No registry match"
              : `${Math.round(node.definition_confidence * 100)}% registry match confidence`
          }
        >
          {titleCase(node.definition_match_state)}
        </span>
        <code>#{node.original_node_id}</code>
      </summary>
      {open ? (
        <div className="node-payload-grid">
          <JsonBlock title="Named/raw inputs" value={node.raw_inputs} />
          <JsonBlock title="Widget values" value={node.raw_widgets} />
          <JsonBlock title="Properties" value={node.raw_properties} />
        </div>
      ) : null}
    </details>
  );
}

function EdgeList({
  edges,
  representation,
  truncated,
}: {
  edges: WorkflowDetail["edges"];
  representation: string;
  truncated: boolean;
}) {
  const [open, setOpen] = useState(false);
  const visibleEdges = representation
    ? edges.filter((edge) => edge.representation === representation)
    : edges;
  return (
    <details
      className="workflow-disclosure edge-disclosure"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {visibleEdges.length} loaded edges{truncated ? " · truncated" : ""}
      </summary>
      {open ? (
        <div className="edge-list">
          {visibleEdges.map((edge) => (
            <div className="edge-row" key={edge.id}>
              <span>{edge.representation === "api_prompt" ? "API" : "VIS"}</span>
              <code>
                {edge.source_node_id}
                {edge.source_output_index === null ? "" : `:${edge.source_output_index}`}
                {" → "}
                {edge.destination_node_id}
                {edge.destination_input_name
                  ? `:${edge.destination_input_name}`
                  : edge.destination_input_index === null
                    ? ""
                    : `:${edge.destination_input_index}`}
              </code>
              <small>{edge.declared_type ?? "untyped"}</small>
            </div>
          ))}
        </div>
      ) : null}
    </details>
  );
}

function RawEvidence({ evidence }: { evidence: WorkflowRawEvidence }) {
  return (
    <div className="raw-evidence-list">
      <JsonBlock title="Container metadata" value={evidence.raw_metadata} />
      <JsonBlock title="Decoded API prompt" value={evidence.api_prompt} />
      <JsonBlock title="Decoded visual workflow" value={evidence.visual_workflow} />
      <JsonBlock title="Exact API prompt text" value={evidence.raw_api_prompt_text} />
      <JsonBlock
        title="Exact visual workflow text"
        value={evidence.raw_visual_workflow_text}
      />
    </div>
  );
}

function JsonBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <section className="json-block">
      <strong>{title}</strong>
      <pre>{prettyValue(value)}</pre>
    </section>
  );
}

function displayValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function prettyValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === undefined) return "";
  return JSON.stringify(value, null, 2);
}
