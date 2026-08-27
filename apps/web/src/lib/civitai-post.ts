import type {
  SemanticObservation,
  WorkflowDetail,
  WorkflowModelUsage,
} from "./api";
import { orderPrompts, promptRoleRank } from "./prompts";

/** A future ComfyGallery backend preparation target; this is not a hosted API request. */
export type CivitaiTarget = "civitai_red" | "civitai_com";

export type PreparedLora = {
  name: string;
  strength: number | string | null;
};

export type PreparedCivitaiPost = {
  target: CivitaiTarget;
  media_id: string;
  post: {
    title: string;
    detail: string;
    tags: string[];
    publish: boolean;
  };
  metadata: {
    positive_prompt: string;
    negative_prompt: string;
    checkpoints: string[];
    loras: PreparedLora[];
  };
};

export type PreparationEvidence = {
  positive_prompt: "observation" | "missing";
  negative_prompt: "observation" | "missing";
  checkpoints: "model_usage" | "observation" | "missing";
  loras: "model_usage" | "observation" | "missing";
};

export type CivitaiPostDraft = PreparedCivitaiPost & {
  evidence: PreparationEvidence;
};

const TARGET_LABELS: Record<CivitaiTarget, string> = {
  civitai_red: "civitai.red",
  civitai_com: "civitai.com",
};

export const defaultCivitaiTarget: CivitaiTarget = "civitai_red";

export function civitaiTargetLabel(target: CivitaiTarget): string {
  return TARGET_LABELS[target];
}

export function filenameTitle(filename: string): string {
  const trimmed = filename.trim();
  const dot = trimmed.lastIndexOf(".");
  return dot > 0 ? trimmed.slice(0, dot) : trimmed;
}

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "";
}

function modelName(usage: WorkflowModelUsage): string {
  return usage.artifact_display_name?.trim() || usage.raw_reference;
}

function orderedUsages(usages: WorkflowModelUsage[]): WorkflowModelUsage[] {
  return [...usages].sort(
    (left, right) =>
      left.usage_order - right.usage_order || left.id.localeCompare(right.id),
  );
}

function orderedObservations(
  observations: SemanticObservation[],
): SemanticObservation[] {
  return [...observations].sort(
    (left, right) =>
      left.id.localeCompare(right.id) || left.created_at.localeCompare(right.created_at),
  );
}

function readStrength(value: unknown): number | string | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) return value.trim();
  return null;
}

export function loraStrength(
  usage: WorkflowModelUsage,
  observations: SemanticObservation[],
): number | string | null {
  const usageStrength = readStrength(usage.evidence.strength);
  if (usageStrength !== null) return usageStrength;
  const observation = observations.find(
    (candidate) =>
      candidate.observation_type === "lora_reference" &&
      candidate.node_id === usage.node_id &&
      candidate.value === usage.raw_reference,
  );
  return readStrength(observation?.evidence.strength);
}

function promptText(
  observations: SemanticObservation[],
  negative: boolean,
): string {
  const prompts = orderPrompts(
    observations.filter((observation) => observation.observation_type === "prompt"),
  );
  const prompt = prompts.find((observation) => {
    const rank = promptRoleRank(observation.role);
    return negative ? rank === 2 : rank === 0;
  });
  return prompt ? textValue(prompt.value) : "";
}

function references(
  workflow: WorkflowDetail | undefined,
  type: "checkpoint_reference" | "lora_reference",
): {
  usages: WorkflowModelUsage[];
  observations: SemanticObservation[];
} {
  return {
    usages: orderedUsages(
      (workflow?.model_usages ?? []).filter(
        (usage) => usage.observation_type === type,
      ),
    ),
    observations: orderedObservations(
      (workflow?.observations ?? []).filter(
        (observation) => observation.observation_type === type,
      ),
    ),
  };
}

export function prepareCivitaiPost(input: {
  mediaId: string;
  originalFilename: string;
  workflow?: WorkflowDetail;
  target?: CivitaiTarget;
}): CivitaiPostDraft {
  const observations = input.workflow?.observations ?? [];
  const checkpoint = references(input.workflow, "checkpoint_reference");
  const lora = references(input.workflow, "lora_reference");
  const checkpoints = checkpoint.usages.length
    ? checkpoint.usages.map(modelName)
    : checkpoint.observations.map((observation) => textValue(observation.value));
  const loras = lora.usages.length
    ? lora.usages.map((usage) => ({
        name: modelName(usage),
        strength: loraStrength(usage, observations),
      }))
    : lora.observations.map((observation) => ({
        name: textValue(observation.value),
        strength: readStrength(observation.evidence.strength),
      }));
  const positivePrompt = promptText(observations, false);
  const negativePrompt = promptText(observations, true);

  return {
    target: input.target ?? defaultCivitaiTarget,
    media_id: input.mediaId,
    post: {
      title: filenameTitle(input.originalFilename),
      detail: "",
      tags: [],
      publish: false,
    },
    metadata: {
      positive_prompt: positivePrompt,
      negative_prompt: negativePrompt,
      checkpoints,
      loras,
    },
    evidence: {
      positive_prompt: positivePrompt ? "observation" : "missing",
      negative_prompt: negativePrompt ? "observation" : "missing",
      checkpoints: checkpoint.usages.length
        ? "model_usage"
        : checkpoint.observations.length
          ? "observation"
          : "missing",
      loras: lora.usages.length
        ? "model_usage"
        : lora.observations.length
          ? "observation"
          : "missing",
    },
  };
}

export function preparedPayload(draft: CivitaiPostDraft): PreparedCivitaiPost {
  return {
    target: draft.target,
    media_id: draft.media_id,
    post: {
      ...draft.post,
      tags: draft.post.tags.map((tag) => tag.trim()).filter(Boolean),
    },
    metadata: {
      ...draft.metadata,
      checkpoints: draft.metadata.checkpoints
        .map((checkpoint) => checkpoint.trim())
        .filter(Boolean),
      loras: draft.metadata.loras.map((lora) => ({ ...lora })),
    },
  };
}
