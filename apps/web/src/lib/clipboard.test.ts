import { afterEach, describe, expect, it, vi } from "vitest";

import { copyText } from "./clipboard";

const originalClipboard = navigator.clipboard;
const originalExecCommand = document.execCommand;

afterEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: originalClipboard,
  });
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: originalExecCommand,
  });
  vi.restoreAllMocks();
});

describe("copyText", () => {
  it("uses the Clipboard API when it is available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });

    await copyText("cinematic portrait");

    expect(writeText).toHaveBeenCalledWith("cinematic portrait");
  });

  it("falls back to a temporary textarea for LAN HTTP deployments", async () => {
    const execCommand = vi.fn().mockReturnValue(true);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await copyText("soft studio light");

    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).not.toBeInTheDocument();
  });

  it("keeps the HTTP fallback inside an active modal and restores focus", async () => {
    const dialog = document.createElement("dialog");
    const button = document.createElement("button");
    dialog.append(button);
    dialog.setAttribute("open", "");
    document.body.append(dialog);
    button.focus();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    const execCommand = vi.fn(() => {
      expect(dialog.querySelector("textarea")).not.toBeNull();
      return true;
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    try {
      await copyText("prompt from registry", dialog);
      expect(execCommand).toHaveBeenCalledWith("copy");
      expect(document.activeElement).toBe(button);
      expect(dialog.querySelector("textarea")).toBeNull();
    } finally {
      dialog.remove();
    }
  });
});
