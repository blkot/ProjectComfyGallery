import {
  isTrustedMessageEvent,
  makeAckMessage,
  parseOpenWorkflowMessage,
} from "./workflow_bridge_protocol.js";

const RESULT_CACHE_LIMIT = 64;

/**
 * Creates the message handler separately from the ComfyUI extension bootstrap
 * so the receiver protocol can be tested without starting a browser.
 */
export function createWorkflowMessageHandler({
  app,
  opener,
  allowedOrigins = new Set(),
  logger = console,
}) {
  const acknowledgements = new Map();
  const pending = new Set();

  return async function handleWorkflowMessage(event) {
    if (!isTrustedMessageEvent(event, opener, allowedOrigins)) return false;

    const message = parseOpenWorkflowMessage(event?.data);
    if (!message) {
      logger.warn?.("[ComfyGallery.WorkflowBridge] Ignored invalid workflow message");
      return false;
    }

    const cached = acknowledgements.get(message.requestId);
    if (cached) {
      postAcknowledgement(event, cached);
      return true;
    }

    // The Gallery retries while the ComfyUI tab is initializing. Do not load a
    // workflow more than once when those retries overlap the first load.
    if (pending.has(message.requestId)) return true;
    pending.add(message.requestId);

    let acknowledgement;
    try {
      const fileName = createWorkflowFileName(message.mediaId);
      if (message.representation === "visual_workflow") {
        await app.loadGraphData(message.workflow, true, true, fileName);
      } else {
        await app.loadApiJson(message.workflow, fileName);
      }
      acknowledgement = { ok: true };
    } catch (error) {
      acknowledgement = { ok: false, error: getErrorMessage(error) };
    } finally {
      pending.delete(message.requestId);
    }

    rememberAcknowledgement(message.requestId, acknowledgement);
    postAcknowledgement(event, acknowledgement);
    return true;
  };

  function rememberAcknowledgement(requestId, acknowledgement) {
    acknowledgements.set(requestId, acknowledgement);
    while (acknowledgements.size > RESULT_CACHE_LIMIT) {
      acknowledgements.delete(acknowledgements.keys().next().value);
    }
  }
}

function postAcknowledgement(event, acknowledgement) {
  const source = event?.source;
  if (!source || typeof source.postMessage !== "function") return;

  source.postMessage(
    makeAckMessage(
      event.data.requestId,
      acknowledgement.ok,
      acknowledgement.error,
    ),
    event.origin,
  );
}

function createWorkflowFileName(mediaId) {
  const safeMediaId = mediaId.replace(/[^a-zA-Z0-9._-]/g, "_").slice(0, 100);
  return `ComfyGallery-${safeMediaId || "workflow"}`;
}

function getErrorMessage(error) {
  if (error instanceof Error && error.message) return error.message;
  return String(error || "ComfyUI could not load the workflow.");
}
