import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";

import { apiRequest, type MediaDetail, type WorkflowDetail } from "../lib/api";
import { copyText } from "../lib/clipboard";
import {
  civitaiTargetLabel,
  type CivitaiPostDraft,
  type CivitaiTarget,
  prepareCivitaiPost,
  preparedPayload,
} from "../lib/civitai-post";

type CopyState = "idle" | "copying" | "copied" | "failed";

function updateLora(
  draft: CivitaiPostDraft,
  index: number,
  field: "name" | "strength",
  value: string,
): CivitaiPostDraft {
  return {
    ...draft,
    metadata: {
      ...draft.metadata,
      loras: draft.metadata.loras.map((lora, loraIndex) =>
        loraIndex === index
          ? { ...lora, [field]: field === "strength" ? value || null : value }
          : lora,
      ),
    },
  };
}

export function CivitaiPostPage() {
  const { mediaId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const [draft, setDraft] = useState<CivitaiPostDraft | null>(null);
  const [draftKey, setDraftKey] = useState("");
  const [copyState, setCopyState] = useState<CopyState>("idle");
  const media = useQuery({
    queryKey: ["media-detail", mediaId],
    queryFn: () => apiRequest<MediaDetail>(`/api/v1/media/${mediaId}`),
    enabled: Boolean(mediaId),
  });
  const workflow = useQuery({
    queryKey: ["media-workflow", mediaId],
    queryFn: () =>
      apiRequest<WorkflowDetail>(
        `/api/v1/media/${mediaId}/workflow?node_limit=1000&edge_limit=3000`,
      ),
    enabled: Boolean(mediaId),
  });
  const sourceKey = `${mediaId}:${media.data?.original_filename ?? ""}:${workflow.data?.snapshot?.id ?? workflow.data?.status ?? ""}`;

  useEffect(() => {
    if (!media.data || draftKey === sourceKey) return;
    queueMicrotask(() => {
      setDraft(
        prepareCivitaiPost({
          mediaId,
          originalFilename: media.data.original_filename,
          workflow: workflow.data,
        }),
      );
      setDraftKey(sourceKey);
      setCopyState("idle");
    });
  }, [draftKey, media.data, mediaId, sourceKey, workflow.data]);

  const prepared = useMemo(
    () => (draft ? preparedPayload(draft) : null),
    [draft],
  );
  const contextSearch = searchParams.toString();
  const detailHref = `/library/${mediaId}${contextSearch ? `?${contextSearch}` : ""}`;

  async function copyPreparedPayload() {
    if (!prepared) return;
    setCopyState("copying");
    try {
      await copyText(JSON.stringify(prepared, null, 2));
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  }

  if (media.isPending) {
    return <main className="page"><p className="muted">Loading media record…</p></main>;
  }
  if (media.isError || !media.data) {
    return (
      <main className="page">
        <p className="notice error-notice">The media record could not be loaded.</p>
        <Link className="secondary-button link-button" to={detailHref}>Back to media</Link>
      </main>
    );
  }
  if (!draft || !prepared) {
    return <main className="page"><p className="muted">Preparing local draft…</p></main>;
  }

  const item = media.data;
  const updateDraft = (updater: (current: CivitaiPostDraft) => CivitaiPostDraft) =>
    setDraft((current) => (current ? updater(current) : current));
  const targetStatus = `${civitaiTargetLabel(draft.target)}: Not connected / connectivity unverified`;

  return (
    <main className="page civitai-post-page">
      <header className="civitai-post-heading">
        <div>
          <p className="kicker">Local preparation only</p>
          <h1>Post to Civitai</h1>
          <p className="muted">Prepare a future ComfyGallery backend-facing draft. This page does not publish.</p>
        </div>
        <Link className="secondary-button link-button" to={detailHref}>Back to media</Link>
      </header>

      <section className="civitai-post-layout">
        <article className="civitai-media-card" aria-label="Current media">
          {item.kind === "image" ? (
            <img src={item.preview_url} alt={item.original_filename} />
          ) : (
            <video src={item.playback_url} controls playsInline preload="metadata" poster={item.preview_url} />
          )}
          <div>
            <p className="kicker">{item.kind}</p>
            <h2>{item.original_filename}</h2>
            <p className="muted">Media ID: {item.id}</p>
          </div>
          {item.kind === "image" ? (
            <p className="notice">Image bytes have a documented future backend-managed upload path.</p>
          ) : (
            <p className="notice">Official image publishing guidance does not prove video upload support. This video draft remains preparation only.</p>
          )}
        </article>

        <section className="civitai-draft-form" aria-label="Prepared Civitai draft">
          <div className="civitai-target-row">
            <label>
              Target
              <select
                value={draft.target}
                onChange={(event) => updateDraft((current) => ({ ...current, target: event.target.value as CivitaiTarget }))}
              >
                <option value="civitai_red">civitai.red</option>
                <option value="civitai_com">civitai.com</option>
              </select>
            </label>
            <p className="notice" role="status">{targetStatus}</p>
          </div>
          <p className="muted small-copy">Connectivity is checked independently for each target: a reachable .com target does not establish .red connectivity.</p>

          <label>
            Title
            <input value={draft.post.title} onChange={(event) => updateDraft((current) => ({ ...current, post: { ...current.post, title: event.target.value } }))} />
          </label>
          <label>
            Detail
            <textarea value={draft.post.detail} onChange={(event) => updateDraft((current) => ({ ...current, post: { ...current.post, detail: event.target.value } }))} />
          </label>
          <label>
            Tags (comma separated)
            <input value={draft.post.tags.join(",")} onChange={(event) => updateDraft((current) => ({ ...current, post: { ...current.post, tags: event.target.value.split(",") } }))} />
          </label>
          <label className="civitai-checkbox">
            <input type="checkbox" checked={draft.post.publish} onChange={(event) => updateDraft((current) => ({ ...current, post: { ...current.post, publish: event.target.checked } }))} />
            Publish intent (stored only in this browser draft)
          </label>
          <label>
            Positive prompt
            <textarea value={draft.metadata.positive_prompt} onChange={(event) => updateDraft((current) => ({ ...current, metadata: { ...current.metadata, positive_prompt: event.target.value } }))} />
          </label>
          <label>
            Negative prompt
            <textarea value={draft.metadata.negative_prompt} onChange={(event) => updateDraft((current) => ({ ...current, metadata: { ...current.metadata, negative_prompt: event.target.value } }))} />
          </label>
          <label>
            Checkpoints (one per line)
            <textarea value={draft.metadata.checkpoints.join("\n")} onChange={(event) => updateDraft((current) => ({ ...current, metadata: { ...current.metadata, checkpoints: event.target.value.split("\n") } }))} />
          </label>
          <section className="civitai-loras" aria-label="Prepared LoRAs">
            <h2>LoRAs</h2>
            {draft.metadata.loras.length ? draft.metadata.loras.map((lora, index) => (
              <div className="civitai-lora-row" key={index}>
                <label>Name<input aria-label={`LoRA ${index + 1} name`} value={lora.name} onChange={(event) => updateDraft((current) => updateLora(current, index, "name", event.target.value))} /></label>
                <label>Strength<input aria-label={`LoRA ${index + 1} strength`} value={lora.strength ?? ""} onChange={(event) => updateDraft((current) => updateLora(current, index, "strength", event.target.value))} /></label>
              </div>
            )) : <p className="muted">No LoRA evidence was extracted; no prepared value is available.</p>}
          </section>
        </section>
      </section>

      <section className="civitai-evidence" aria-label="Evidence mapping">
        <h2>Evidence → prepared fields</h2>
        <dl>
          <div><dt>Positive prompt</dt><dd>{draft.evidence.positive_prompt === "observation" ? "Semantic observation" : "Missing evidence"}</dd></div>
          <div><dt>Negative prompt</dt><dd>{draft.evidence.negative_prompt === "observation" ? "Semantic observation" : "Missing evidence"}</dd></div>
          <div><dt>Checkpoints</dt><dd>{draft.evidence.checkpoints === "model_usage" ? "Workflow model usage" : draft.evidence.checkpoints === "observation" ? "Semantic observation fallback" : "Missing evidence"}</dd></div>
          <div><dt>LoRAs</dt><dd>{draft.evidence.loras === "model_usage" ? "Workflow model usage (strength may use matching observation)" : draft.evidence.loras === "observation" ? "Semantic observation fallback" : "Missing evidence"}</dd></div>
        </dl>
        {workflow.isError ? <p className="notice error-notice">Workflow evidence could not be loaded. The empty preparation fields remain editable.</p> : workflow.data?.snapshot ? null : <p className="notice">No workflow snapshot is available; fields without evidence stay empty and editable.</p>}
      </section>

      <section className="civitai-payload" aria-label="Prepared JSON">
        <h2>Prepared JSON</h2>
        <pre>{JSON.stringify(prepared, null, 2)}</pre>
        <div className="civitai-payload-actions">
          <button className="secondary-button" type="button" disabled={copyState === "copying"} onClick={() => void copyPreparedPayload()}>
            {copyState === "copying" ? "Copying…" : "Copy prepared JSON"}
          </button>
          <button className="primary-button" type="button" disabled>Publishing not connected</button>
        </div>
        <p role={copyState === "failed" ? "alert" : "status"} className={copyState === "failed" ? "notice error-notice" : "notice"}>
          {copyState === "copied" ? "Prepared JSON copied." : copyState === "failed" ? "Prepared JSON could not be copied." : "Backend unavailable: publishing cannot run from this page."}
        </p>
      </section>

      <aside className="civitai-future-boundary">
        <strong>Future backend boundary</strong>
        <p>A future backend, not this page, must hold credentials, read managed media bytes, and call the hosted MCP. It must support explicit server-side proxy configuration (for example WinPC or Mac) and independent connectivity checks per target.</p>
      </aside>
    </main>
  );
}
