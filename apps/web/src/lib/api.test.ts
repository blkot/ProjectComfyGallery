import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest, readCookie } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "cg_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

describe("API client", () => {
  it("reads an encoded cookie", () => {
    document.cookie = "cg_csrf=token%20value; path=/";
    expect(readCookie("cg_csrf")).toBe("token%20value");
  });

  it("adds the CSRF header to state-changing requests", async () => {
    document.cookie = "cg_csrf=csrf-value; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await apiRequest<{ ok: boolean }>("/example", {
      method: "POST",
      body: JSON.stringify({ name: "test" }),
    });

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("x-csrf-token")).toBe("csrf-value");
    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe("include");
  });

  it("lets the browser set multipart boundaries for FormData", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const body = new FormData();
    body.append("files", new Blob(["image"]), "image.png");

    await apiRequest<{ ok: boolean }>("/example", { method: "POST", body });

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.has("content-type")).toBe(false);
  });

  it("maps the stable error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "not_ready", message: "Service is starting" },
        }),
        { status: 503, headers: { "content-type": "application/json" } },
      ),
    );

    await expect(apiRequest("/health/ready")).rejects.toEqual(
      expect.objectContaining({
        status: 503,
        code: "not_ready",
        message: "Service is starting",
      }),
    );
  });
});
