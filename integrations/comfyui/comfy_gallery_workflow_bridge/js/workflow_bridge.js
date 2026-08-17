import { app } from "../../scripts/app.js";

import {
  makeReadyMessage,
  parseAllowedOrigins,
} from "./workflow_bridge_protocol.js";
import { createWorkflowMessageHandler } from "./workflow_bridge_receiver.js";

const ALLOWED_ORIGINS_STORAGE_KEY = "comfy-gallery-workflow.allowed-origins";
const GLOBAL_ALLOWED_ORIGINS_KEY = "__COMFY_GALLERY_ALLOWED_ORIGINS__";

app.registerExtension({
  name: "ComfyGallery.WorkflowBridge",

  async setup() {
    const opener = window.opener;
    const handleWorkflowMessage = createWorkflowMessageHandler({
      app,
      opener,
      allowedOrigins: readAllowedOrigins(),
    });

    window.addEventListener("message", handleWorkflowMessage);
    sendReady(opener);
  },
});

function sendReady(opener) {
  if (!opener || opener.closed || typeof opener.postMessage !== "function") return;

  // The ready message contains no workflow data. The Gallery validates the
  // source and origin before sending the workflow payload.
  try {
    opener.postMessage(makeReadyMessage(), "*");
  } catch (error) {
    console.warn("[ComfyGallery.WorkflowBridge] Could not announce readiness", error);
  }
}

function readAllowedOrigins() {
  const globalValue = globalThis[GLOBAL_ALLOWED_ORIGINS_KEY];
  if (globalValue !== undefined) return parseAllowedOrigins(globalValue);

  try {
    return parseAllowedOrigins(
      window.localStorage.getItem(ALLOWED_ORIGINS_STORAGE_KEY) || "",
    );
  } catch {
    return new Set();
  }
}
