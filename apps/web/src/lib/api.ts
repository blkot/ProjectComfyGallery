export type User = {
  id: string;
  username: string;
};

export type SessionResponse = {
  user: User;
};

export type SystemStatus = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  checks: Record<
    string,
    {
      status: "ok" | "warning" | "error" | string;
      detail: string | null;
      data: Record<string, unknown>;
    }
  >;
  warnings: string[];
};

export type PortableExport = {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  export_schema_version: string;
  requested_options: Record<string, unknown>;
  sha256: string | null;
  byte_size: number | null;
  table_counts: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  download_url: string | null;
};

export type ApiTokenRecord = {
  id: string;
  label: string;
  token_prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type CreatedApiToken = ApiTokenRecord & {
  token: string;
};

export type MediaListItem = {
  id: string;
  kind: "image" | "video";
  status: string;
  detected_format: string | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  container: string | null;
  video_codec: string | null;
  warning_count: number;
  byte_size: number;
  original_filename: string;
  source_count: number;
  workflow_status: string;
  evaluation_state: "not_started" | "in_progress" | "complete";
  is_trash: boolean;
  spatial_available: boolean;
  prefer_spatial_playback: boolean;
  spatial_view_preferred: boolean;
  favorite: boolean;
  file_created_at: string;
  created_at: string;
  preview_url: string;
};

export type MediaPage = {
  items: MediaListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type MediaNavigation = {
  media_id: string;
  position: number;
  total: number;
  previous_id: string | null;
  previous_position: number | null;
  next_id: string | null;
  next_position: number | null;
};

export type MediaPlaybackPreference = {
  media_id: string;
  prefer_spatial_playback: boolean;
  spatial_view_preferred: boolean;
  updated_at: string;
};

export type MediaFavorite = {
  media_id: string;
  favorite: boolean;
  updated_at: string;
};

export type Derivative = {
  id: string;
  kind: string;
  recipe_version: string;
  mime_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  container: string | null;
  codec: string | null;
};

export type MediaVariant = {
  id: string;
  role: string;
  status: "ready";
  mime_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  frame_rate: number | null;
  container: string | null;
  video_codec: string | null;
  audio_codec: string | null;
  converter_name: string | null;
  converter_version: string | null;
  ready_at: string;
  content_url: string;
};

export type MediaVariantImportStatus = {
  id: string;
  media_id: string;
  role: string;
  status: "staging" | "processing" | "ready" | "failed";
  is_active: boolean;
  sha256: string | null;
  byte_size: number | null;
  original_filename: string;
  original_extension: string | null;
  detected_format: string | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  duration_seconds: number | null;
  frame_rate: number | null;
  container: string | null;
  video_codec: string | null;
  audio_codec: string | null;
  validation_data: Record<string, unknown>;
  converter_name: string | null;
  converter_version: string | null;
  source_asset_sha256: string | null;
  ready_at: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type SourceOccurrence = {
  id: string;
  source_root_id: string;
  relative_path: string;
  original_filename: string;
  byte_size: number;
  mtime_ns: number;
  sha256: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  superseded_at: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type MediaDetail = Omit<MediaListItem, "source_count"> & {
  frame_rate: number | null;
  audio_codec: string | null;
  probe_data: Record<string, unknown>;
  last_error_code: string | null;
  last_error_message: string | null;
  sha256: string;
  original_extension: string | null;
  updated_at: string;
  playback_url: string;
  original_url: string;
  workflow_url: string;
  derivatives: Derivative[];
  variants: MediaVariant[];
  sources: SourceOccurrence[];
};

export type WorkflowValue = {
  id: string;
  locator: string;
  input_name: string | null;
  input_index: number | null;
  value_kind: string;
  raw_value: unknown;
  normalized_text: string | null;
};

export type WorkflowNode = {
  id: string;
  node_definition_id: string | null;
  definition_match_state: string;
  definition_confidence: number | null;
  representation: "api_prompt" | "visual_workflow";
  ordinal: number;
  original_node_id: string;
  class_type: string;
  title: string | null;
  module_hint: string | null;
  mode: number | null;
  raw_properties: Record<string, unknown>;
  raw_widgets: unknown[];
  raw_inputs: Record<string, unknown> | unknown[];
  values: WorkflowValue[];
};

export type WorkflowModelUsage = {
  id: string;
  node_id: string | null;
  model_reference_id: string;
  artifact_id: string | null;
  observation_type: string;
  raw_reference: string;
  artifact_display_name: string | null;
  architecture_family: string | null;
  lineage: string | null;
  pipeline_pattern: string;
  slot: string;
  usage_order: number;
  confidence: number;
  correction_state: string;
  evidence: Record<string, unknown>;
};

export type WorkflowEdge = {
  id: string;
  representation: "api_prompt" | "visual_workflow";
  ordinal: number;
  original_link_id: string | null;
  source_node_id: string;
  source_output_index: number | null;
  destination_node_id: string;
  destination_input_index: number | null;
  destination_input_name: string | null;
  declared_type: string | null;
  raw_link: Record<string, unknown> | unknown[];
};

export type SemanticObservation = {
  id: string;
  node_id: string | null;
  observation_type: string;
  role: string | null;
  value: unknown;
  confidence: number;
  correction_state: string;
  evidence: Record<string, unknown>;
  created_at: string;
};

export type ExtractionRun = {
  id: string;
  extractor_name: string;
  extractor_version: string;
  graph_version: string;
  configuration_hash: string;
  reason: string;
  status: string;
  is_current: boolean;
  observation_count: number;
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type WorkflowSnapshot = {
  id: string;
  media_id: string;
  reader_name: string;
  reader_version: string;
  source_carrier: string;
  evidence_sha256: string;
  api_prompt_status: string;
  visual_workflow_status: string;
  parse_status: string;
  issue_details: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  graph_version: string | null;
  api_node_count: number;
  visual_node_count: number;
  edge_count: number;
  created_at: string;
};

export type WorkflowDetail = {
  media_id: string;
  status: string;
  snapshot: WorkflowSnapshot | null;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  observations: SemanticObservation[];
  model_usages: WorkflowModelUsage[];
  runs: ExtractionRun[];
  node_limit: number;
  node_offset: number;
  nodes_truncated: boolean;
  edges_truncated: boolean;
  raw_url: string | null;
};

export type WorkflowRawEvidence = {
  snapshot_id: string;
  evidence_sha256: string;
  raw_metadata: Record<string, unknown>;
  raw_api_prompt_text: string | null;
  raw_visual_workflow_text: string | null;
  api_prompt: Record<string, unknown> | null;
  visual_workflow: Record<string, unknown> | null;
};

export type WorkflowBulkReprocessResult = {
  mode: "missing" | "all";
  matched_count: number;
  queued_count: number;
  already_active_count: number;
  queue_failed_count: number;
  job_ids: string[];
};

export type SourceRoot = {
  id: string;
  name: string;
  path: string;
  enabled: boolean;
  last_scan_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ScanBatch = {
  id: string;
  source_root_id: string;
  status: string;
  discovered_count: number;
  skipped_count: number;
  imported_count: number;
  duplicate_count: number;
  failed_count: number;
  missing_count: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
};

export type UploadItem = {
  id: string;
  batch_id: string;
  media_id: string | null;
  original_filename: string;
  byte_size: number;
  status: string;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
};

export type UploadBatch = {
  id: string;
  status: string;
  total_count: number;
  queued_count: number;
  completed_count: number;
  duplicate_count: number;
  failed_count: number;
  created_at: string;
  completed_at: string | null;
  items: UploadItem[];
};

export type Job = {
  id: string;
  kind: string;
  queue: string;
  status: string;
  resource_type: string;
  resource_id: string;
  stage: string | null;
  attempt_count: number;
  progress_current: number;
  progress_total: number;
  cancel_requested: boolean;
  error_code: string | null;
  error_message: string | null;
  error_details: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type VariantImportAccepted = {
  variant: MediaVariantImportStatus;
  job: Job;
};

export type RegistrySyncRun = {
  id: string;
  registry_kind: string;
  source_url: string;
  requested_options: Record<string, unknown>;
  status: string;
  current_stage: string | null;
  stage_status: Record<string, unknown>;
  counts: Record<string, unknown>;
  source_versions: Record<string, unknown>;
  node_snapshot_id: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type RegistrySyncCreated = {
  sync_run: RegistrySyncRun;
  job: Job;
};

export type NodeMapping = {
  id: string;
  node_definition_id: string;
  locator: string;
  input_name: string | null;
  input_index: number | null;
  semantic_type: string;
  role: string | null;
  source: string;
  confidence: number;
  state: string;
  correction_state: string;
  evidence: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type NodeDefinition = {
  id: string;
  class_type: string;
  python_module: string;
  schema_fingerprint: string;
  source_kind: string;
  display_name: string | null;
  category: string | null;
  is_present: boolean;
  mapping_state: string;
  workflow_occurrence_count: number;
  first_seen_at: string;
  last_seen_at: string;
};

export type NodeDefinitionDetail = NodeDefinition & {
  description: string | null;
  input_schema: Record<string, unknown>;
  output_schema: unknown[];
  raw_definition: Record<string, unknown>;
  mappings: NodeMapping[];
};

export type NodeDefinitionPage = {
  items: NodeDefinition[];
  total: number;
  limit: number;
  offset: number;
};

export type NodeMappingCreated = {
  mapping: NodeMapping;
  job: Job;
};

export type ModelArtifact = {
  id: string;
  artifact_type: string;
  display_name: string;
  file_name: string | null;
  file_path: string | null;
  sha256: string | null;
  provider: string;
  provider_model_id: string | null;
  provider_version_id: string | null;
  provider_url: string | null;
  identity_state: string;
  availability: string;
  enrichment_state: string;
  architecture_family: string | null;
  lineage: string | null;
  variant: string | null;
  precision: string | null;
  quantization: string | null;
  manual_overrides: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
};

export type ModelArtifactDetail = ModelArtifact & {
  raw_inventory: Record<string, unknown>;
  raw_provider_metadata: Record<string, unknown>;
};

export type ModelArtifactPage = {
  items: ModelArtifact[];
  total: number;
  limit: number;
  offset: number;
};

export type ModelArtifactUpdated = {
  artifact: ModelArtifact;
  job: Job;
};

export type ModelReference = {
  id: string;
  artifact_id: string | null;
  identity_group_id: string | null;
  reference_type: string;
  raw_value: string;
  normalized_value: string;
  availability: string;
  resolution_state: string;
  match_method: string | null;
  confidence: number | null;
  occurrence_count: number;
  candidate_artifact_ids: string[];
  manual_override: boolean;
  first_seen_at: string;
  last_seen_at: string;
};

export type ModelReferencePage = {
  items: ModelReference[];
  total: number;
  limit: number;
  offset: number;
};

export type ModelReferenceLinked = {
  reference: ModelReference;
  job: Job;
};

export type ModelReferenceAliasCandidate = {
  canonical_key: string;
  display_name: string;
  reference_type: string;
  evidence_method: string;
  confidence: number;
  conflict_reason: string | null;
  occurrence_count: number;
  references: ModelReference[];
};

export type ModelReferenceGroup = {
  id: string;
  reference_type: string;
  canonical_key: string;
  display_name: string;
  source: string;
  confidence: number;
  status: string;
  created_at: string;
  updated_at: string;
  references: ModelReference[];
};

export type ModelReferenceFilterOption = {
  reference_id: string;
  identity_group_id: string | null;
  reference_type: string;
  display_name: string;
  occurrence_count: number;
  alias_count: number;
};

export type LoraSeriesMember = {
  id: string;
  series_id: string;
  model_reference_id: string;
  artifact_id: string | null;
  training_step: number;
  source: string;
  correction_state: string;
  created_at: string;
  updated_at: string;
};

export type LoraSeries = {
  id: string;
  opaque_name: string;
  display_name: string;
  source: string;
  correction_state: string;
  created_at: string;
  updated_at: string;
  members: LoraSeriesMember[];
};

export type ComparisonGroupMember = {
  artifact_id: string;
  display_name: string;
  artifact_type: string;
  architecture_family: string | null;
  lineage: string | null;
};

export type ComparisonGroup = {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  members: ComparisonGroupMember[];
};

export type EvaluationCriterion = {
  criterion_version_id: string;
  stable_key: string;
  module: string;
  version: number;
  label: string;
  guidance: string;
  anchor_0: string;
  anchor_5: string;
  anchor_10: string;
  required: boolean;
  allow_na: boolean;
};

export type EvaluationScore = {
  criterion_version_id: string;
  state: "scored" | "na";
  value: number | null;
  na_reason: string | null;
  updated_at: string;
};

export type Evaluation = {
  id: string;
  media_id: string;
  template_id: string;
  template_name: string;
  template_version: number;
  module: string;
  evaluation_kind: "base" | "supplemental";
  progress_state: "not_started" | "in_progress" | "complete";
  is_trash: boolean;
  version: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  criteria: EvaluationCriterion[];
  scores: EvaluationScore[];
};

export type ReviewSession = {
  id: string;
  name: string | null;
  source_kind: string;
  scope_snapshot: Record<string, unknown>;
  ordering_mode: string;
  random_seed: number | null;
  optional_modules: string[];
  status: "active" | "finished" | "abandoned";
  current_cursor: number;
  candidate_count: number;
  progress_counts: Record<string, number>;
  last_opened_at: string;
  created_at: string;
  updated_at: string;
};

export type ReviewPrompt = {
  role: string | null;
  label: string;
  text: string;
};

export type MediaEvaluationModule = {
  module: string;
  label: string;
  required: boolean;
  enabled: boolean;
  has_saved_scores: boolean;
  progress_state: "not_started" | "in_progress" | "complete" | null;
};

export type MediaEvaluationContext = {
  media_id: string;
  progress_state: "not_started" | "in_progress" | "complete";
  is_trash: boolean;
  enabled_modules: string[];
  available_modules: MediaEvaluationModule[];
  prompts: ReviewPrompt[];
  evaluations: Evaluation[];
};

export type ReviewItem = {
  session: ReviewSession;
  position: number;
  media: {
    id: string;
    kind: "image" | "video";
    preview_url: string;
    playback_url: string;
    width: number | null;
    height: number | null;
    duration_seconds: number | null;
  };
  prompts: ReviewPrompt[];
  evaluations: Evaluation[];
};

export type ReviewSummary = {
  not_started_count: number;
  in_progress_count: number;
  complete_count: number;
  trash_count: number;
  active_session_count: number;
};

export type Collection = {
  id: string;
  name: string;
  description: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type MediaTag = {
  id: string;
  name: string;
  color: string | null;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export type SavedFilter = {
  id: string;
  name: string;
  expression: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
};

export type AnalysisReportType =
  | "checkpoint"
  | "checkpoint_pair"
  | "lora"
  | "lora_training_series"
  | "checkpoint_lora_matrix"
  | "lora_combination";

export type AnalysisFilter = {
  module: "core" | "character";
  media_kind: "image" | "video" | null;
  template_ids: string[];
  collection_id: string | null;
  tag_id: string | null;
  source_root_id: string | null;
  architecture_family: string | null;
  pipeline_pattern: string | null;
  slots: string[];
  artifact_ids: string[];
  comparison_group_id: string | null;
  lora_series_id: string | null;
  include_trash: boolean;
};

export type AnalysisSpec = {
  report_type: AnalysisReportType;
  criterion_keys: string[];
  compatibility_mode: "shared" | "available";
  any_role: boolean;
  reference_group_key: string | null;
  weighting_profile_id: string | null;
};

export type AnalysisOption = {
  id: string;
  label: string;
  metadata: Record<string, unknown>;
};

export type AnalysisOptions = {
  templates: AnalysisOption[];
  criteria: AnalysisOption[];
  artifacts: AnalysisOption[];
  comparison_groups: AnalysisOption[];
  lora_series: AnalysisOption[];
  architecture_families: string[];
  pipeline_patterns: string[];
  slots: string[];
};

export type WeightingProfile = {
  id: string;
  stable_key: string;
  version: number;
  name: string;
  description: string | null;
  weights: Record<string, number>;
  default_weight: number;
  is_builtin: boolean;
  created_at: string;
};

export type AnalysisResult = {
  id: string | null;
  group_key: string;
  group_label: string;
  dimensions: Record<string, unknown>;
  criterion_key: string;
  criterion_label: string;
  eligible_count: number;
  scored_count: number;
  na_count: number;
  not_collected_count: number;
  trash_count: number;
  coverage: number;
  mean: number | null;
  median: number | null;
  minimum: number | null;
  maximum: number | null;
  q1: number | null;
  q3: number | null;
  ci_low: number | null;
  ci_high: number | null;
  reference_group_key: string | null;
  difference_from_reference: number | null;
  effect_size: number | null;
  evidence_strength: "insufficient" | "suggestive" | "stronger";
  histogram: number[];
  context: Record<string, unknown>;
};

export type AnalysisReport = {
  report_type: AnalysisReportType;
  media_count: number;
  excluded_count: number;
  group_count: number;
  effective_criteria: Array<{ key: string; label: string }>;
  warnings: string[];
  context: Record<string, unknown>;
  results: AnalysisResult[];
};

export type AnalysisRunSummary = {
  id: string;
  title: string;
  report_type: AnalysisReportType;
  status: string;
  parent_run_id: string | null;
  weighting_profile_id: string;
  media_count: number;
  excluded_count: number;
  group_count: number;
  warnings: string[];
  created_at: string;
  completed_at: string | null;
};

export type AnalysisRun = AnalysisRunSummary & {
  filter_spec: Record<string, unknown>;
  report_spec: Record<string, unknown>;
  calculation_version: string;
  effective_criteria: Array<{ key: string; label: string }>;
  context: Record<string, unknown>;
  results: AnalysisResult[];
};

export type AnalysisMedia = {
  media_id: string;
  evaluation_id: string | null;
  included: boolean;
  exclusion_reason: string | null;
  composite_score: number | null;
  group_keys: unknown[];
  preview_url: string;
};

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly details?: unknown;

  constructor(status: number, payload: ErrorEnvelope) {
    super(payload.error?.message ?? `Request failed with status ${status}`);
    this.name = "ApiClientError";
    this.status = status;
    this.code = payload.error?.code ?? "request_failed";
    this.requestId = payload.error?.request_id;
    this.details = payload.error?.details;
  }
}

export function readCookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  return document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
    ?.slice(prefix.length);
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  if (init.body && !isFormData && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  const method = (init.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = readCookie("cg_csrf");
    if (csrfToken) {
      headers.set("x-csrf-token", decodeURIComponent(csrfToken));
    }
  }

  const response = await fetch(path, {
    ...init,
    credentials: "include",
    headers,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ErrorEnvelope;
    throw new ApiClientError(response.status, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
