export const PROTOCOL_VERSION = 1;

export const READY_MESSAGE_TYPE = "comfy-gallery-workflow-ready";
export const OPEN_MESSAGE_TYPE = "comfy-gallery-open-workflow";
export const ACK_MESSAGE_TYPE = "comfy-gallery-open-workflow-ack";

export const MAX_WORKFLOW_BYTES = 8 * 1024 * 1024;

export function makeReadyMessage() {
  return {
    type: READY_MESSAGE_TYPE,
    version: PROTOCOL_VERSION,
  };
}

export function makeAckMessage(requestId, ok, error) {
  const message = {
    type: ACK_MESSAGE_TYPE,
    version: PROTOCOL_VERSION,
    requestId,
    ok,
  };

  if (!ok && error) {
    message.error = String(error).slice(0, 500);
  }

  return message;
}

export function parseOpenWorkflowMessage(value) {
  if (!isRecord(value)) return null;
  if (value.type !== OPEN_MESSAGE_TYPE || value.version !== PROTOCOL_VERSION) {
    return null;
  }

  const requestId = stringWithin(value.requestId, 256);
  const mediaId = stringWithin(value.mediaId, 256);
  const representation = value.representation;
  if (
    !requestId ||
    !mediaId ||
    (representation !== "visual_workflow" && representation !== "api_prompt") ||
    !isRecord(value.workflow)
  ) {
    return null;
  }

  try {
    if (JSON.stringify(value.workflow).length > MAX_WORKFLOW_BYTES) return null;
  } catch {
    return null;
  }

  return {
    requestId,
    mediaId,
    representation,
    workflow: value.workflow,
  };
}

export function isTrustedMessageEvent(event, opener, allowedOrigins) {
  if (!opener || event?.source !== opener) return false;
  if (typeof event?.origin !== "string" || event.origin === "null") return false;

  // With no configured allowlist, the opener relationship is the capability:
  // ComfyUI only accepts messages from the tab that opened it. Deployments that
  // need a stricter policy can provide one through localStorage.
  return allowedOrigins.size === 0 || allowedOrigins.has(event.origin);
}

export function parseAllowedOrigins(value) {
  const values = Array.isArray(value) ? value : String(value ?? "").split(",");
  return new Set(
    values
      .map((origin) => String(origin).trim())
      .filter((origin) => origin && origin !== "null"),
  );
}

function isRecord(value) {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function stringWithin(value, maxLength) {
  return typeof value === "string" && value.length > 0 && value.length <= maxLength
    ? value
    : null;
}
