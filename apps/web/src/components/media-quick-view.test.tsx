import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { RefObject } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MediaDetail, MediaNavigation, PromptRegistryLookup, WorkflowDetail } from "../lib/api";
import { MediaQuickView, type MediaQuickViewProps } from "./media-quick-view";

const { apiRequestMock, copyTextMock, favoriteClickMock, ratingClickMock } = vi.hoisted(() => ({
  apiRequestMock: vi.fn(),
  copyTextMock: vi.fn(),
  favoriteClickMock: vi.fn(),
  ratingClickMock: vi.fn(),
}));

vi.mock("../lib/api", async () => ({
  ...await vi.importActual<typeof import("../lib/api")>("../lib/api"),
  apiRequest: apiRequestMock,
}));
vi.mock("../lib/clipboard", () => ({ copyText: copyTextMock }));
vi.mock("./media-action-toolbar", () => ({
  MediaActionToolbar: ({ favoriteButtonRef, contentRatingShortcutRef }: {
    favoriteButtonRef?: RefObject<HTMLButtonElement | null>;
    contentRatingShortcutRef?: RefObject<HTMLButtonElement | null>;
  }) => <div role="group" aria-label="Media actions">
    <button ref={favoriteButtonRef} onClick={favoriteClickMock}>Favorite</button>
    <button ref={contentRatingShortcutRef} onClick={ratingClickMock}>Rating</button>
  </div>,
}));

const media: MediaDetail = {
  id: "media-1", kind: "image", status: "ready", detected_format: "png", mime_type: "image/png",
  width: 2048, height: 3072, duration_seconds: null, container: null, video_codec: null,
  warning_count: 0, byte_size: 123456, original_filename: "portrait.png", workflow_status: "ready",
  evaluation_state: "not_started", is_trash: false, spatial_available: false,
  prefer_spatial_playback: false, spatial_view_preferred: false, favorite: false,
  content_rating: "sfw", file_created_at: "2026-11-06T00:00:00Z", created_at: "2026-11-06T00:00:00Z",
  preview_url: "/previews/media-1.jpg", original_url: "/originals/media-1.png",
  playback_url: "/originals/media-1.png", workflow_url: "/media-1/workflow",
  frame_rate: null, audio_codec: null, probe_data: {}, last_error_code: null, last_error_message: null,
  sha256: "test", original_extension: ".png", updated_at: "2026-11-06T00:00:00Z",
  derivatives: [], variants: [], sources: [],
};
const navigation: MediaNavigation = {
  media_id: "media-1", position: 2, total: 6,
  previous_id: "media-0", previous_position: 1, next_id: "media-2", next_position: 3,
};
const workflow: WorkflowDetail = {
  media_id: "media-1", status: "ready", snapshot: null, nodes: [], edges: [], observations: [],
  model_usages: [], runs: [], node_limit: 1, node_offset: 0, nodes_truncated: true,
  edges_truncated: true, raw_url: null,
  display_fields: {
    prompt_id: { value: "portrait-00042", source: "save_node", node_id: "1", job_id: null },
    character_lora: { value: "Alice.safetensors", source: "save_node", node_id: "1", job_id: null },
    lora_list: { value: [["Alice.safetensors", 0.8, 0.6]], source: "save_node", node_id: "1", job_id: null },
    prompt: { value: "embedded prompt must not be used", source: "save_node", node_id: "1", job_id: null },
  },
};
const registry: PromptRegistryLookup = {
  prompt_id: "portrait-00042", source: "portrait", index: "00042", media: [], total_media: 6,
  limit: 1, offset: 0,
  entry: {
    id: "prompt-42", source: "portrait", index: "00042", prompt: "Registry portrait\nsoft morning light",
    negative_prompt: null, metadata: {}, origin: "import", media_count: 6,
    created_at: "2026-11-06T00:00:00Z", updated_at: "2026-11-06T00:00:00Z",
  },
};

let showModalMock = vi.fn<() => void>();
let closeMock = vi.fn<() => void>();
const originalShowModal = HTMLDialogElement.prototype.showModal;
const originalClose = HTMLDialogElement.prototype.close;

beforeEach(() => {
  showModalMock = vi.fn(function (this: HTMLDialogElement) { this.setAttribute("open", ""); });
  closeMock = vi.fn(function (this: HTMLDialogElement) { this.removeAttribute("open"); });
  HTMLDialogElement.prototype.showModal = showModalMock;
  HTMLDialogElement.prototype.close = closeMock;
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  apiRequestMock.mockImplementation(defaultRequest);
  copyTextMock.mockResolvedValue(undefined);
});

afterEach(() => {
  cleanup();
  HTMLDialogElement.prototype.showModal = originalShowModal;
  HTMLDialogElement.prototype.close = originalClose;
  vi.restoreAllMocks();
  vi.clearAllMocks();
  document.body.style.overflow = "";
});

function defaultRequest(path: string) {
  if (path.includes("/workflow?")) return Promise.resolve(workflow);
  if (path.startsWith("/api/v1/prompt-registry/lookup?")) return Promise.resolve(registry);
  const id = path.match(/^\/api\/v1\/media\/(media-\d+)$/)?.[1];
  if (id) return Promise.resolve({ ...media, id, original_url: `/originals/${id}.png` });
  return Promise.reject(new Error(`Unexpected request: ${path}`));
}

function renderPreview(overrides: Partial<MediaQuickViewProps> = {}, suppliedClient?: QueryClient) {
  const queryClient = suppliedClient ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const props: MediaQuickViewProps = {
    mediaId: "media-1", navigation, onSeek: vi.fn(), onClose: vi.fn(),
    fullDetailHref: "/library/media-1", slideshowHref: "/slideshow?start=media-1",
    civitaiHref: "/civitai?media=media-1", ...overrides,
  };
  function view(nextProps: MediaQuickViewProps) {
    return <QueryClientProvider client={queryClient}>
      <MemoryRouter><MediaQuickView {...nextProps} /></MemoryRouter>
    </QueryClientProvider>;
  }
  const rendered = render(view(props));
  return { ...rendered, props, queryClient, rerenderPreview: (next: Partial<MediaQuickViewProps>) => {
    rendered.rerender(view({ ...props, ...next }));
  } };
}

describe("MediaQuickView", () => {
  it("keeps a loaded frame visible while the next image in a four-media scope is decoding", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    for (const id of ["media-1", "media-2", "media-3", "media-4"]) {
      client.setQueryData(["media-detail", id], { ...media, id, original_url: `/originals/${id}.png` });
    }
    const { rerenderPreview } = renderPreview({}, client);
    fireEvent.load(await screen.findByRole("img", { name: "portrait.png" }));
    for (const index of [2, 3, 4, 3, 2, 1]) {
      const previousFrame = document.querySelector('img[data-loaded="true"]');
      expect(previousFrame).not.toBeNull();
      rerenderPreview({ mediaId: `media-${index}`, navigation: {
        media_id: `media-${index}`, position: index, total: 4,
        previous_id: index > 1 ? `media-${index - 1}` : null, previous_position: index > 1 ? index - 1 : null,
        next_id: index < 4 ? `media-${index + 1}` : null, next_position: index < 4 ? index + 1 : null,
      } });
      expect(previousFrame).toBeInTheDocument();
      const incoming = await waitFor(() => {
        const image = document.querySelector(`img[src="/originals/media-${index}.png"]`);
        expect(image).not.toBeNull();
        return image!;
      });
      fireEvent.load(incoming);
    }
  });

  it("renders the original image, compact authoritative metadata and the registry's positive prompt", async () => {
    const { queryClient } = renderPreview();
    const image = await screen.findByRole("img", { name: "portrait.png" });
    expect(image).toHaveAttribute("src", "/originals/media-1.png");
    expect(image).toHaveAttribute("data-loaded", "false");
    fireEvent.load(image);
    expect(image).toHaveAttribute("data-loaded", "true");
    expect(document.querySelector(".media-image-stage-placeholder")).toBeNull();
    expect(await screen.findByText("Registry portrait soft morning light")).toBeInTheDocument();
    expect(screen.queryByText("embedded prompt must not be used")).toBeNull();
    expect(screen.getByRole("link", { name: "portrait-00042" })).toHaveAttribute("href", "/registries/prompts?prompt_id=portrait-00042");
    expect(screen.getByRole("link", { name: "Open full details" })).toHaveAttribute("href", "/library/media-1");
    const loras = screen.getByText("LoRA list · 1").closest("details")!;
    expect(loras).not.toHaveAttribute("open");
    fireEvent.click(loras.querySelector("summary")!);
    expect(loras).toHaveAttribute("open");
    expect(screen.getByText("0.80")).toBeInTheDocument();
    expect(screen.getByText("0.60")).toBeInTheDocument();
    expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/media/media-1/workflow?node_limit=1&edge_limit=1");
    expect(queryClient.getQueryData(["media-workflow", "media-1"])).toBeUndefined();
    fireEvent.click(screen.getByRole("button", { name: "Copy positive prompt" }));
    await waitFor(() => expect(copyTextMock).toHaveBeenCalledWith(registry.entry!.prompt, screen.getByRole("dialog")));
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });

  it("reuses the current usage lookup instead of fetching the same registry prompt again", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData(["prompt-registry-usage", "prompt_id=Portrait+-+42&group_by_character=true"], {
      ...registry, prompt_id: "Portrait - 42", source: "Portrait", index: "42",
    });
    renderPreview({}, queryClient);
    expect(await screen.findByText("Registry portrait soft morning light")).toBeInTheDocument();
    expect(apiRequestMock.mock.calls.some(([path]) => String(path).startsWith("/api/v1/prompt-registry/lookup"))).toBe(false);
  });

  it("does not mislabel embedded prompt text as a registry prompt when no ID was recorded", async () => {
    apiRequestMock.mockImplementation((path: string) => path.includes("/workflow?")
      ? Promise.resolve({ ...workflow, display_fields: { prompt: workflow.display_fields?.prompt } })
      : defaultRequest(path));
    renderPreview();
    expect(await screen.findByText("Not recorded")).toBeInTheDocument();
    expect(screen.getByText("A recorded Prompt ID is needed to resolve the registry prompt.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy positive prompt" })).toBeDisabled();
    expect(screen.queryByText("embedded prompt must not be used")).toBeNull();
    expect(apiRequestMock.mock.calls.some(([path]) => String(path).startsWith("/api/v1/prompt-registry/lookup"))).toBe(false);
  });

  it("distinguishes an unregistered ID from a failed registry request", async () => {
    apiRequestMock.mockImplementation((path: string) => path.startsWith("/api/v1/prompt-registry/lookup")
      ? Promise.resolve({ ...registry, entry: null }) : defaultRequest(path));
    const first = renderPreview();
    expect(await screen.findByText("This Prompt ID is not registered.")).toBeInTheDocument();
    first.unmount();
    apiRequestMock.mockImplementation((path: string) => path.startsWith("/api/v1/prompt-registry/lookup")
      ? Promise.reject(new Error("offline")) : defaultRequest(path));
    renderPreview();
    expect(await screen.findByText("Registry prompt could not be loaded.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copy positive prompt" })).toBeDisabled();
    expect(screen.queryByText("embedded prompt must not be used")).toBeNull();
  });

  it("does not claim a prompt ID is missing when workflow metadata failed to load", async () => {
    apiRequestMock.mockImplementation((path: string) => path.includes("/workflow?")
      ? Promise.reject(new Error("offline")) : defaultRequest(path));
    renderPreview();
    expect(await screen.findByText("Metadata could not be loaded.")).toBeInTheDocument();
    expect(screen.getByText("Prompt lookup is unavailable until metadata can be loaded.")).toBeInTheDocument();
    expect(screen.queryByText("Not recorded")).toBeNull();
    expect(screen.getByRole("button", { name: "Copy positive prompt" })).toBeDisabled();
  });

  it("keeps keyboard and pointer actions in the media context, never in text or native controls", async () => {
    const { props } = renderPreview();
    const image = await screen.findByRole("img", { name: "portrait.png" });
    fireEvent.load(image);
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(props.onSeek).toHaveBeenNthCalledWith(1, "media-2", 3);
    expect(props.onSeek).toHaveBeenNthCalledWith(2, "media-0", 1);
    fireEvent.keyDown(dialog, { key: "f" });
    fireEvent.keyDown(dialog, { key: "n" });
    expect(favoriteClickMock).toHaveBeenCalledTimes(1);
    expect(ratingClickMock).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "f", ctrlKey: true });
    fireEvent.keyDown(dialog, { key: "n", repeat: true });
    fireEvent.keyDown(screen.getByRole("link", { name: "Open full details" }), { key: "ArrowRight" });
    const input = document.createElement("input");
    dialog.append(input);
    fireEvent.keyDown(input, { key: "f" });
    fireEvent.keyDown(input, { key: "ArrowRight" });
    input.remove();
    expect(favoriteClickMock).toHaveBeenCalledTimes(1);
    expect(ratingClickMock).toHaveBeenCalledTimes(1);
    expect(props.onSeek).toHaveBeenCalledTimes(2);
    fireEvent.wheel(screen.getByRole("complementary", { name: "Media information" }), { deltaY: 120 });
    expect(props.onSeek).toHaveBeenCalledTimes(2);
    const now = vi.spyOn(Date, "now").mockReturnValue(1000);
    fireEvent.wheel(image, { deltaY: 120 });
    fireEvent.wheel(image, { deltaY: 120 });
    expect(props.onSeek).toHaveBeenCalledTimes(3);
    now.mockReturnValue(1400);
    fireEvent.wheel(image, { deltaY: -120 });
    expect(props.onSeek).toHaveBeenLastCalledWith("media-0", 1);
    fireEvent(image, new MouseEvent("auxclick", { button: 1, bubbles: true }));
    expect(favoriteClickMock).toHaveBeenCalledTimes(2);
  });

  it("waits for decoding before swapping and blocks wrong-media actions while retaining the old frame", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["media-detail", "media-1"], media);
    client.setQueryData(["media-detail", "media-2"], { ...media, id: "media-2", original_url: "/originals/media-2.png", original_filename: "next.png" });
    const { props, rerenderPreview } = renderPreview({}, client);
    const original = await screen.findByRole("img", { name: "portrait.png" });
    fireEvent.load(original);
    let finishDecode!: () => void;
    const decode = new Promise<void>((resolve) => { finishDecode = resolve; });
    rerenderPreview({ mediaId: "media-2", navigation: { ...navigation, media_id: "media-2", next_id: "media-3" } });
    const incoming = document.querySelector('img[src="/originals/media-2.png"]') as HTMLImageElement;
    incoming.decode = vi.fn(() => decode);
    fireEvent.load(incoming);
    expect(original).toHaveAttribute("data-loaded", "true");
    expect(incoming).toHaveAttribute("data-loaded", "false");
    expect(screen.getByText(/Loading next.png.*Previous image remains visible/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Favorite" })).toBeDisabled();
    expect(document.querySelector(".media-quick-view-actions")).toHaveAttribute("inert");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "f" });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "n" });
    fireEvent(original, new MouseEvent("auxclick", { button: 1, bubbles: true }));
    expect(favoriteClickMock).not.toHaveBeenCalled();
    expect(ratingClickMock).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowRight" });
    expect(props.onSeek).toHaveBeenCalledWith("media-3", navigation.next_position);
    await act(async () => { finishDecode(); await decode; });
    expect(incoming).toHaveAttribute("data-loaded", "true");
    expect(original).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Favorite" })).toBeEnabled();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "f" });
    expect(favoriteClickMock).toHaveBeenCalledTimes(1);
  });

  it("ignores a superseded decode and keeps the previous frame visibly labeled on a target failure", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    for (const id of ["media-1", "media-2", "media-3"]) client.setQueryData(["media-detail", id], { ...media, id, original_url: `/originals/${id}.png` });
    const { rerenderPreview } = renderPreview({}, client);
    const original = await screen.findByRole("img", { name: "portrait.png" });
    fireEvent.load(original);
    rerenderPreview({ mediaId: "media-2" });
    const second = document.querySelector('img[src="/originals/media-2.png"]') as HTMLImageElement;
    let finishDecode!: () => void;
    const decode = new Promise<void>((resolve) => { finishDecode = resolve; });
    second.decode = vi.fn(() => decode);
    fireEvent.load(second);
    rerenderPreview({ mediaId: "media-3" });
    await act(async () => { finishDecode(); await decode; });
    expect(original).toHaveAttribute("data-loaded", "true");
    expect(second).not.toBeInTheDocument();
    const third = document.querySelector('img[src="/originals/media-3.png"]') as HTMLImageElement;
    fireEvent.error(third);
    expect(screen.getByRole("alert")).toHaveTextContent("Could not load the requested media. Previous image remains visible.");
    expect(screen.getByRole("button", { name: "Favorite" })).toBeDisabled();
    expect(original).toBeInTheDocument();
  });

  it("reveals an already-complete original after decode without depending on a fresh load event", async () => {
    vi.spyOn(HTMLImageElement.prototype, "complete", "get").mockReturnValue(true);
    vi.spyOn(HTMLImageElement.prototype, "naturalWidth", "get").mockReturnValue(2048);
    renderPreview();
    await waitFor(() => expect(document.querySelector('.media-image-stage-original')).toHaveAttribute("data-loaded", "true"));
    expect(screen.getByRole("button", { name: "Favorite" })).toBeEnabled();
  });

  it("does not reuse image readiness after the presenter was unmounted for a video", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["media-detail", "media-1"], media);
    client.setQueryData(["media-detail", "media-2"], { ...media, id: "media-2", kind: "video", playback_url: "/video.mp4" });
    const { rerenderPreview } = renderPreview({}, client);
    fireEvent.load(await screen.findByRole("img", { name: "portrait.png" }));
    expect(screen.getByRole("button", { name: "Favorite" })).toBeEnabled();
    rerenderPreview({ mediaId: "media-2" });
    expect(document.querySelector("video")).not.toBeNull();
    rerenderPreview({ mediaId: "media-1" });
    expect(screen.getByRole("button", { name: "Favorite" })).toBeDisabled();
    fireEvent.load(await screen.findByRole("img", { name: "portrait.png" }));
    expect(screen.getByRole("button", { name: "Favorite" })).toBeEnabled();
  });

  it("disables stale or loading scope navigation without removing the visible media", async () => {
    const { props, rerenderPreview } = renderPreview({ navigationPending: true });
    await screen.findByRole("img", { name: "portrait.png" });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowRight" });
    expect(screen.getByRole("button", { name: "Next media" })).toBeDisabled();
    expect(props.onSeek).not.toHaveBeenCalled();
    rerenderPreview({ navigationPending: false, navigationError: true });
    expect(screen.getByRole("button", { name: "Next media" })).toBeDisabled();
    expect(screen.getByText("Navigation unavailable")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "portrait.png" })).toBeInTheDocument();
    rerenderPreview({ navigationPending: false, navigation: { ...navigation, media_id: "media-2" } });
    expect(screen.getByRole("button", { name: "Next media" })).toBeDisabled();
  });

  it("retains known neighbors when a mutation removes the current media from the scope", async () => {
    const { props } = renderPreview({ navigationError: true, navigationOutsideScope: true });
    await screen.findByRole("img", { name: "portrait.png" });
    expect(screen.getByText("Outside view")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next media" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Previous media" })).toBeEnabled();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowRight" });
    expect(props.onSeek).toHaveBeenCalledWith("media-2", 3);
  });

  it("uses a unified close callback for Escape, backdrop and close button", async () => {
    const { props } = renderPreview();
    await screen.findByRole("img", { name: "portrait.png" });
    const dialog = screen.getByRole("dialog");
    fireEvent(dialog, new Event("cancel", { bubbles: true, cancelable: true }));
    expect(props.onClose).toHaveBeenCalledTimes(1);
    fireEvent.mouseDown(dialog, { clientX: -1, clientY: -1 });
    fireEvent.click(dialog, { clientX: -1, clientY: -1 });
    expect(props.onClose).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Close media preview" }));
    expect(props.onClose).toHaveBeenCalledTimes(3);
    fireEvent.mouseDown(screen.getByRole("img", { name: "portrait.png" }));
    fireEvent.click(dialog, { clientX: -1, clientY: -1 });
    expect(props.onClose).toHaveBeenCalledTimes(3);
  });

  it("keeps the dialog and scroll lock mounted across seek, and prefetches only adjacent originals", async () => {
    document.body.style.overflow = "auto";
    const { rerenderPreview, unmount } = renderPreview();
    await screen.findByRole("img", { name: "portrait.png" });
    await waitFor(() => expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/media/media-2"));
    expect(apiRequestMock).toHaveBeenCalledWith("/api/v1/media/media-0");
    expect(apiRequestMock).not.toHaveBeenCalledWith(expect.stringContaining("media-2/workflow"));
    expect(showModalMock).toHaveBeenCalledTimes(1);
    expect(document.body.style.overflow).toBe("hidden");
    rerenderPreview({ mediaId: "media-2", navigation: { ...navigation, media_id: "media-2", position: 3 } });
    await waitFor(() => expect(screen.getByRole("img", { name: "portrait.png" })).toHaveAttribute("src", "/originals/media-2.png"));
    expect(showModalMock).toHaveBeenCalledTimes(1);
    expect(closeMock).not.toHaveBeenCalled();
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(closeMock).toHaveBeenCalledTimes(1);
    expect(document.body.style.overflow).toBe("auto");
  });

  it("leaves video controls and audio native, and releases playback on seek or close", async () => {
    apiRequestMock.mockImplementation((path: string) => path === "/api/v1/media/media-1"
      ? Promise.resolve({ ...media, kind: "video", playback_url: "/originals/media-1.mp4" })
      : defaultRequest(path));
    const { props, rerenderPreview } = renderPreview();
    const video = await screen.findByLabelText("portrait.png", { selector: "video" }) as HTMLVideoElement;
    expect(video).toHaveAttribute("src", "/originals/media-1.mp4");
    expect(video.controls).toBe(true);
    expect(video.muted).toBe(false);
    fireEvent.keyDown(video, { key: "ArrowRight" });
    fireEvent.wheel(video, { deltaY: 120 });
    fireEvent(video, new MouseEvent("auxclick", { button: 1, bubbles: true }));
    expect(props.onSeek).not.toHaveBeenCalled();
    expect(favoriteClickMock).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("dialog"), { code: "Space", key: " " });
    expect(video.play).toHaveBeenCalledTimes(1);
    rerenderPreview({ mediaId: "media-2", navigation: undefined });
    await screen.findByRole("img", { name: "portrait.png" });
    expect(video.pause).toHaveBeenCalled();
    expect(video).not.toHaveAttribute("src");
    expect(video.load).toHaveBeenCalled();
  });
});
