import test from "node:test";
import assert from "node:assert/strict";

import { createWorkflowMessageHandler } from "../js/workflow_bridge_receiver.js";

function createEvent(opener, data, origin = "http://gallery.test") {
  return {
    source: opener,
    origin,
    data,
  };
}

function visualMessage(requestId = "request-1") {
  return {
    type: "comfy-gallery-open-workflow",
    version: 1,
    requestId,
    mediaId: "media/1",
    representation: "visual_workflow",
    workflow: { nodes: [], links: [] },
  };
}

test("loads a visual workflow and acknowledges it", async () => {
  const acknowledgements = [];
  const opener = {
    postMessage(message, targetOrigin) {
      acknowledgements.push({ message, targetOrigin });
    },
  };
  const calls = [];
  const handle = createWorkflowMessageHandler({
    app: {
      async loadGraphData(...args) {
        calls.push(args);
      },
      loadApiJson() {
        throw new Error("API loader should not be used");
      },
    },
    opener,
  });

  await handle(createEvent(opener, visualMessage()));

  assert.equal(calls.length, 1);
  assert.deepEqual(calls[0].slice(0, 4), [
    { nodes: [], links: [] },
    true,
    true,
    "ComfyGallery-media_1",
  ]);
  assert.deepEqual(acknowledgements, [
    {
      message: {
        type: "comfy-gallery-open-workflow-ack",
        version: 1,
        requestId: "request-1",
        ok: true,
      },
      targetOrigin: "http://gallery.test",
    },
  ]);
});

test("loads an API prompt and re-acknowledges duplicate retries without reloading", async () => {
  const acknowledgements = [];
  const opener = {
    postMessage(message, targetOrigin) {
      acknowledgements.push({ message, targetOrigin });
    },
  };
  const calls = [];
  const handle = createWorkflowMessageHandler({
    app: {
      loadGraphData() {
        throw new Error("visual loader should not be used");
      },
      loadApiJson(...args) {
        calls.push(args);
      },
    },
    opener,
  });
  const data = {
    ...visualMessage("request-2"),
    representation: "api_prompt",
    workflow: { "1": { class_type: "LoadImage", inputs: {} } },
  };

  await handle(createEvent(opener, data));
  await handle(createEvent(opener, data));

  assert.deepEqual(calls, [
    [{ "1": { class_type: "LoadImage", inputs: {} } }, "ComfyGallery-media_1"],
  ]);
  assert.equal(acknowledgements.length, 2);
  assert.equal(acknowledgements[0].message.ok, true);
  assert.equal(acknowledgements[1].message.ok, true);
});

test("ignores messages from a different source or disallowed origin", async () => {
  const acknowledgements = [];
  const opener = { postMessage: (...args) => acknowledgements.push(args) };
  const calls = [];
  const handle = createWorkflowMessageHandler({
    app: { loadGraphData: (...args) => calls.push(args), loadApiJson() {} },
    opener,
    allowedOrigins: new Set(["http://gallery.test"]),
  });

  assert.equal(
    await handle(createEvent({}, visualMessage("request-3"))),
    false,
  );
  assert.equal(
    await handle(createEvent(opener, visualMessage("request-4"), "http://other.test")),
    false,
  );
  assert.equal(calls.length, 0);
  assert.equal(acknowledgements.length, 0);
});

test("acknowledges loader failures with an actionable error", async () => {
  const acknowledgements = [];
  const opener = {
    postMessage(message) {
      acknowledgements.push(message);
    },
  };
  const handle = createWorkflowMessageHandler({
    app: {
      async loadGraphData() {
        throw new Error("missing custom node: LoadImage");
      },
      loadApiJson() {},
    },
    opener,
  });

  await handle(createEvent(opener, visualMessage("request-5")));

  assert.deepEqual(acknowledgements, [
    {
      type: "comfy-gallery-open-workflow-ack",
      version: 1,
      requestId: "request-5",
      ok: false,
      error: "missing custom node: LoadImage",
    },
  ]);
});
