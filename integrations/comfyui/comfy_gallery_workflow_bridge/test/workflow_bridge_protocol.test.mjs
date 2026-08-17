import test from "node:test";
import assert from "node:assert/strict";

import {
  makeAckMessage,
  makeReadyMessage,
  parseOpenWorkflowMessage,
  isTrustedMessageEvent,
} from "../js/workflow_bridge_protocol.js";

const opener = {};

test("accepts a visual workflow message", () => {
  const message = parseOpenWorkflowMessage({
    type: "comfy-gallery-open-workflow",
    version: 1,
    requestId: "request-1",
    mediaId: "media-1",
    representation: "visual_workflow",
    workflow: { nodes: [], links: [] },
  });

  assert.deepEqual(message, {
    requestId: "request-1",
    mediaId: "media-1",
    representation: "visual_workflow",
    workflow: { nodes: [], links: [] },
  });
});

test("accepts an API prompt message", () => {
  const message = parseOpenWorkflowMessage({
    type: "comfy-gallery-open-workflow",
    version: 1,
    requestId: "request-2",
    mediaId: "media-2",
    representation: "api_prompt",
    workflow: { "1": { class_type: "LoadImage", inputs: {} } },
  });

  assert.equal(message?.representation, "api_prompt");
  assert.deepEqual(message?.workflow, {
    "1": { class_type: "LoadImage", inputs: {} },
  });
});

test("rejects malformed or oversized workflow messages", () => {
  assert.equal(parseOpenWorkflowMessage(null), null);
  assert.equal(
    parseOpenWorkflowMessage({
      type: "comfy-gallery-open-workflow",
      version: 2,
      requestId: "request-3",
      mediaId: "media-3",
      representation: "visual_workflow",
      workflow: {},
    }),
    null,
  );
  assert.equal(
    parseOpenWorkflowMessage({
      type: "comfy-gallery-open-workflow",
      version: 1,
      requestId: "request-4",
      mediaId: "media-4",
      representation: "visual_workflow",
      workflow: { payload: "x".repeat(8 * 1024 * 1024) },
    }),
    null,
  );
});

test("requires the opener and an allowed origin", () => {
  assert.equal(
    isTrustedMessageEvent(
      { source: opener, origin: "http://gallery.test" },
      opener,
      new Set(["http://gallery.test"]),
    ),
    true,
  );
  assert.equal(
    isTrustedMessageEvent(
      { source: {}, origin: "http://gallery.test" },
      opener,
      new Set(["http://gallery.test"]),
    ),
    false,
  );
  assert.equal(
    isTrustedMessageEvent(
      { source: opener, origin: "http://other.test" },
      opener,
      new Set(["http://gallery.test"]),
    ),
    false,
  );
  assert.equal(
    isTrustedMessageEvent(
      { source: opener, origin: "null" },
      opener,
      new Set(),
    ),
    false,
  );
});

test("creates protocol ready and acknowledgement messages", () => {
  assert.deepEqual(makeReadyMessage(), {
    type: "comfy-gallery-workflow-ready",
    version: 1,
  });
  assert.deepEqual(makeAckMessage("request-5", true), {
    type: "comfy-gallery-open-workflow-ack",
    version: 1,
    requestId: "request-5",
    ok: true,
  });
  assert.deepEqual(makeAckMessage("request-6", false, "load failed"), {
    type: "comfy-gallery-open-workflow-ack",
    version: 1,
    requestId: "request-6",
    ok: false,
    error: "load failed",
  });
});
