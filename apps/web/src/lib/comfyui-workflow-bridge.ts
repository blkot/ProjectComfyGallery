import type { WorkflowRawEvidence } from "./api";

export const COMFYUI_WORKFLOW_PROTOCOL_VERSION = 1;
export const COMFYUI_WORKFLOW_WINDOW_NAME = "comfyui-workflow";

const READY_MESSAGE_TYPE = "comfy-gallery-workflow-ready";
const OPEN_MESSAGE_TYPE = "comfy-gallery-open-workflow";
const ACK_MESSAGE_TYPE = "comfy-gallery-open-workflow-ack";
const MAX_RETRIES = 3;
const RETRY_DELAYS_MS = [0, 250, 1_000] as const;
const ACK_TIMEOUT_MS = 3_500;

export type ComfyUiTab = {
  window: Window;
  origin: string;
};

type WorkflowRepresentation = "visual_workflow" | "api_prompt";

type WorkflowBridgeMessage = {
  type: typeof OPEN_MESSAGE_TYPE;
  version: number;
  requestId: string;
  mediaId: string;
  representation: WorkflowRepresentation;
  workflow: Record<string, unknown>;
};

type WorkflowReadyMessage = {
  type: typeof READY_MESSAGE_TYPE;
  version: number;
};

type WorkflowAckMessage = {
  type: typeof ACK_MESSAGE_TYPE;
  version: number;
  requestId: string;
  ok: boolean;
  error?: string;
};

export function getComfyUiTarget(
  configuredUrl = import.meta.env.VITE_COMFYUI_UI_URL,
): { href: string; origin: string } {
  const trimmedConfiguredUrl = configuredUrl?.trim();
  const fallbackUrl = getDefaultComfyUiUrl();
  const rawUrl = trimmedConfiguredUrl || fallbackUrl;

  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    throw new Error(
      "The ComfyUI URL is invalid. Set VITE_COMFYUI_UI_URL to an http(s) URL.",
    );
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("The ComfyUI URL must use http or https.");
  }

  return { href: parsed.href, origin: parsed.origin };
}

export function openComfyUiTab(): ComfyUiTab {
  const target = getComfyUiTarget();
  const comfyUiWindow = window.open(target.href, COMFYUI_WORKFLOW_WINDOW_NAME);
  if (!comfyUiWindow) {
    throw new Error(
      "The ComfyUI tab was blocked. Allow pop-ups for ComfyGallery and try again.",
    );
  }
  return { window: comfyUiWindow, origin: target.origin };
}

export async function sendWorkflowToComfyUi(
  tab: ComfyUiTab,
  mediaId: string,
  evidence: WorkflowRawEvidence,
): Promise<void> {
  const selected = selectWorkflow(evidence);
  if (!selected) {
    throw new Error("No decoded workflow is available for this media.");
  }
  if (tab.window.closed) {
    throw new Error("The ComfyUI tab was closed before the workflow was sent.");
  }

  const requestId = createRequestId();
  const message: WorkflowBridgeMessage = {
    type: OPEN_MESSAGE_TYPE,
    version: COMFYUI_WORKFLOW_PROTOCOL_VERSION,
    requestId,
    mediaId,
    representation: selected.representation,
    workflow: selected.workflow,
  };

  return new Promise<void>((resolve, reject) => {
    let settled = false;
    const retryTimers: number[] = [];
    let timeoutTimer = 0;

    const cleanup = () => {
      window.removeEventListener("message", handleMessage);
      retryTimers.forEach((timer) => window.clearTimeout(timer));
      window.clearTimeout(timeoutTimer);
    };

    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) reject(error);
      else resolve();
    };

    const postWorkflow = () => {
      if (settled || tab.window.closed) return;
      try {
        tab.window.postMessage(message, tab.origin);
      } catch {
        finish(new Error("The workflow could not be sent to the ComfyUI tab."));
      }
    };

    function handleMessage(event: MessageEvent<unknown>) {
      if (event.source !== tab.window || event.origin !== tab.origin) return;
      if (!isRecord(event.data)) return;
      const data = event.data as Partial<WorkflowReadyMessage | WorkflowAckMessage>;
      if (data.version !== COMFYUI_WORKFLOW_PROTOCOL_VERSION) return;

      if (data.type === READY_MESSAGE_TYPE) {
        postWorkflow();
        return;
      }
      if (data.type !== ACK_MESSAGE_TYPE || data.requestId !== requestId) return;

      if (data.ok) {
        finish();
      } else {
        finish(
          new Error(
            data.error || "ComfyUI rejected the workflow message.",
          ),
        );
      }
    }

    window.addEventListener("message", handleMessage);
    postWorkflow();
    RETRY_DELAYS_MS.slice(1, MAX_RETRIES).forEach((delay) => {
      retryTimers.push(window.setTimeout(postWorkflow, delay));
    });
    timeoutTimer = window.setTimeout(() => {
      finish(
        new Error(
          "ComfyUI did not acknowledge the workflow. Install the Gallery workflow bridge extension in ComfyUI.",
        ),
      );
    }, ACK_TIMEOUT_MS);
  });
}

function selectWorkflow(
  evidence: WorkflowRawEvidence,
): { representation: WorkflowRepresentation; workflow: Record<string, unknown> } | null {
  if (isWorkflowObject(evidence.visual_workflow)) {
    return {
      representation: "visual_workflow",
      workflow: evidence.visual_workflow,
    };
  }
  if (isWorkflowObject(evidence.api_prompt)) {
    return { representation: "api_prompt", workflow: evidence.api_prompt };
  }
  return null;
}

function isWorkflowObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function getDefaultComfyUiUrl(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8188/";
  const url = new URL(window.location.href);
  url.port = "8188";
  url.pathname = "/";
  url.search = "";
  url.hash = "";
  return url.href;
}

function createRequestId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `workflow-${Date.now()}-${crypto.getRandomValues(new Uint32Array(2)).join("-")}`;
}
