import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  ApiClientError,
  apiRequest,
  type MediaDetail,
  type MediaVariantImportStatus,
  type VariantImportAccepted,
} from "../lib/api";
import { formatBytes, titleCase } from "../lib/format";

type SpatialVariantAttachmentProps = {
  media: Pick<MediaDetail, "id" | "kind" | "sha256" | "variants">;
  createIdempotencyKey?: () => string;
  pollInterval?: number;
};

const terminalStatuses = new Set(["ready", "failed", "duplicate"]);
const manualConverterName = "ComfyGallery web manual upload";

function defaultIdempotencyKey() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
  return [
    value.slice(0, 4).join(""),
    value.slice(4, 6).join(""),
    value.slice(6, 8).join(""),
    value.slice(8, 10).join(""),
    value.slice(10).join(""),
  ].join("-");
}

function errorMessage(error: Error | null) {
  if (!error) return null;
  if (error instanceof ApiClientError) {
    return `${error.code}: ${error.message}`;
  }
  return "The spatial video could not be uploaded. Check the connection and try again.";
}

export function SpatialVariantAttachment({
  media,
  createIdempotencyKey = defaultIdempotencyKey,
  pollInterval = 2_000,
}: SpatialVariantAttachmentProps) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const handledReadyVariant = useRef<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [variantId, setVariantId] = useState<string | null>(null);

  const importStatus = useQuery({
    queryKey: ["media-variant-import", media.id, variantId],
    queryFn: () =>
      apiRequest<MediaVariantImportStatus>(
        `/api/v1/media/${media.id}/variant-imports/${variantId}`,
      ),
    enabled: Boolean(variantId),
    retry: (failureCount, error) =>
      !(
        error instanceof ApiClientError &&
        (error.status === 401 || error.status === 403)
      ) && failureCount < 2,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalStatuses.has(status) ? false : pollInterval;
    },
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const body = new FormData();
      body.append("file", file);
      body.append("role", "spatial_video");
      body.append("source_asset_sha256", media.sha256);
      body.append("converter_name", manualConverterName);
      return apiRequest<VariantImportAccepted>(
        `/api/v1/media/${media.id}/variant-imports`,
        {
          method: "POST",
          headers: {
            "Idempotency-Key": createIdempotencyKey(),
          },
          body,
        },
      );
    },
    onMutate: () => {
      setVariantId(null);
    },
    onSuccess: async (response) => {
      setVariantId(response.variant.id);
      await queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const status = importStatus.data?.status;
  const lastErrorCode = importStatus.data?.last_error_code;
  const duplicateImport = status === "duplicate";
  const legacyDuplicateConflict =
    status === "failed" && lastErrorCode === "VARIANT_DUPLICATE_CONFLICT";
  const resolvedImport =
    status === "ready" || duplicateImport || legacyDuplicateConflict;
  useEffect(() => {
    if (
      !resolvedImport ||
      !variantId ||
      handledReadyVariant.current === variantId
    ) {
      return;
    }
    handledReadyVariant.current = variantId;
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["media-detail", media.id] }),
      queryClient.invalidateQueries({ queryKey: ["media"] }),
      queryClient.invalidateQueries({ queryKey: ["media-navigation"] }),
      queryClient.invalidateQueries({ queryKey: ["jobs"] }),
    ]);
  }, [media.id, queryClient, resolvedImport, variantId]);

  if (media.kind !== "video") return null;

  const replacement = media.variants.length > 0;
  const failedImport = status === "failed" && !legacyDuplicateConflict;
  const isProcessing =
    status === "staging" ||
    status === "processing" ||
    (Boolean(variantId) && importStatus.isPending);
  const canSubmit =
    Boolean(selectedFile) &&
    !upload.isPending &&
    !isProcessing &&
    !resolvedImport;
  const backendFailure = importStatus.data
    ? [importStatus.data.last_error_code, importStatus.data.last_error_message]
        .filter(Boolean)
        .join(": ")
    : null;
  const pollingError = errorMessage(importStatus.error);
  const uploadError = errorMessage(upload.error);

  function resetPanel() {
    upload.reset();
    setPanelOpen(false);
    setSelectedFile(null);
    setVariantId(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="spatial-variant-attachment">
      <div className="spatial-variant-attachment-heading">
        <div>
          <strong>Attach spatial video</strong>
          <small>Add an Apple spatial-video variant to this media record.</small>
        </div>
        {!panelOpen ? (
          <button
            className="secondary-button"
            type="button"
            onClick={() => setPanelOpen(true)}
          >
            {replacement ? "Replace variant" : "Attach variant"}
          </button>
        ) : null}
      </div>

      {panelOpen ? (
        <section
          className="spatial-variant-attachment-panel"
          role="dialog"
          aria-labelledby="spatial-variant-attachment-title"
        >
          <div>
            <p className="kicker">Manual upload</p>
            <h4 id="spatial-variant-attachment-title">
              {replacement
                ? "Replace the active spatial video"
                : "Attach a spatial video"}
            </h4>
            <p className="muted">
              Choose a QuickTime MOV or compatible MP4 file. The gallery validates
              the file in the background after upload.
            </p>
          </div>

          {replacement ? (
            <p className="spatial-variant-replacement-note">
              The current variant stays active while this file is checked. It is
              replaced atomically only after the new variant is ready.
            </p>
          ) : null}

          <label className="spatial-variant-file">
            Spatial video file
            <input
              ref={fileInputRef}
              type="file"
              accept=".mov,.mp4,.m4v,video/quicktime,video/mp4"
              disabled={upload.isPending || isProcessing || resolvedImport}
              onChange={(event) => {
                upload.reset();
                setVariantId(null);
                setSelectedFile(event.target.files?.[0] ?? null);
              }}
            />
          </label>

          {selectedFile ? (
            <div className="spatial-variant-file-summary" aria-live="polite">
              <span>
                <strong>{selectedFile.name}</strong>
                <small>{selectedFile.type || "Video file"}</small>
              </span>
              <span>{formatBytes(selectedFile.size)}</span>
            </div>
          ) : null}

          {upload.isPending ? (
            <p className="notice spatial-variant-progress" role="status">
              <strong>Uploading</strong>
              <span>Sending the selected file to the gallery…</span>
            </p>
          ) : null}
          {!upload.isPending && isProcessing ? (
            <p className="notice spatial-variant-progress" role="status">
              <strong>{titleCase(status ?? "processing")}</strong>
              <span>
                The upload is complete. The worker is validating the spatial
                video…
              </span>
            </p>
          ) : null}
          {status === "ready" ? (
            <p className="notice spatial-variant-success" role="status">
              <strong>Spatial video ready</strong>
              <span>
                The validated variant is now available to spatial clients.
              </span>
            </p>
          ) : null}
          {duplicateImport ? (
            <p className="notice spatial-variant-success" role="status">
              <strong>Spatial video already attached</strong>
              <span>
                These exact bytes are already the active spatial variant. No
                duplicate file was stored.
              </span>
            </p>
          ) : null}
          {legacyDuplicateConflict ? (
            <p className="notice" role="status">
              <strong>Spatial video already imported</strong>
              <span>
                The gallery already stores these exact bytes. No duplicate file
                was created; the media record has been refreshed.
              </span>
            </p>
          ) : null}
          {!resolvedImport && (uploadError || backendFailure || pollingError) ? (
            <p className="notice error-notice" role="alert">
              <strong>
                {failedImport ? "Spatial video validation failed" : "Upload failed"}
              </strong>
              <span>{backendFailure || uploadError || pollingError}</span>
            </p>
          ) : null}

          <div className="spatial-variant-attachment-actions">
            <button
              className="secondary-button"
              type="button"
              disabled={upload.isPending || isProcessing}
              onClick={resetPanel}
            >
              {resolvedImport ? "Done" : "Cancel"}
            </button>
            {!resolvedImport ? (
              <button
                className="primary-button"
                type="button"
                disabled={!canSubmit}
                onClick={() => {
                  if (selectedFile) upload.mutate(selectedFile);
                }}
              >
                {upload.error || failedImport ? "Retry upload" : "Confirm upload"}
              </button>
            ) : null}
          </div>
        </section>
      ) : null}
    </div>
  );
}
