import { useCallback, useEffect, useRef, useState } from "react";
import type { MediaDetail } from "../lib/api";
import "./media-image-stage.css";

type ImageMedia = Pick<MediaDetail, "id" | "original_url" | "original_filename" | "preview_url">;

/** The previous decoded frame survives until the requested original is ready. */
export function MediaImageStage({ mediaId, media, failed, onReady, onRetry }: {
  mediaId: string;
  media?: ImageMedia;
  failed?: boolean;
  onReady: (id: string | null) => void;
  onRetry?: () => void;
}) {
  const [displayed, setDisplayed] = useState<ImageMedia | null>(null);
  const [failedId, setFailedId] = useState("");
  // Switching to a video discards this presenter and its decoded DOM frame.
  // The toolbar must not reuse that old readiness when returning to the image.
  useEffect(() => () => onReady(null), [onReady]);
  const current = media?.id === mediaId ? media : undefined;
  const isReady = displayed?.id === mediaId;
  const isFailed = failed || failedId === mediaId;
  const frames = displayed && displayed.id !== current?.id
    ? [displayed, ...(current ? [current] : [])]
    : current ? [current] : [];
  const acceptFrame = useCallback((item: ImageMedia) => {
    if (item.id !== mediaId) return;
    setDisplayed(item);
    setFailedId("");
    onReady(item.id);
  }, [mediaId, onReady]);

  return <div className="media-image-stage" data-pending={!isReady || undefined} aria-busy={!isReady}>
    {!displayed && current && !isFailed ? <img className="media-image-stage-placeholder"
      src={current.preview_url} alt="" aria-hidden="true" /> : null}
    {frames.map((item) => <ImageFrame key={item.id} media={item}
      displayed={displayed?.id === item.id} hiddenFromAccessibility={Boolean(displayed && displayed.id !== item.id)}
      onReady={acceptFrame} onError={() => setFailedId(item.id)} />)}
    {!isReady ? <p className="media-image-stage-notice" role={isFailed ? "alert" : "status"}>
      {isFailed ? <>Could not load the requested media.{displayed ? " Previous image remains visible." : ""}
        {current ? <> <a href={current.original_url}>Open original</a></> : null}
        {failed && onRetry ? <> <button type="button" onClick={onRetry}>Retry</button></> : null}</>
        : <>Loading {current?.original_filename ?? "requested media"}…{displayed ? " Previous image remains visible." : ""}</>}
    </p> : null}
  </div>;
}

function ImageFrame({ media, displayed, hiddenFromAccessibility, onReady, onError }: {
  media: ImageMedia;
  displayed: boolean;
  hiddenFromAccessibility: boolean;
  onReady: (media: ImageMedia) => void;
  onError: () => void;
}) {
  const imageRef = useRef<HTMLImageElement>(null);
  const decodingRef = useRef(false);
  const prepareFrame = useCallback(async (image: HTMLImageElement) => {
    if (decodingRef.current) return;
    decodingRef.current = true;
    try {
      if (image.decode) await image.decode();
      if (imageRef.current === image) onReady(media);
    } catch {
      if (imageRef.current === image) onError();
    }
  }, [media, onReady, onError]);
  useEffect(() => {
    const image = imageRef.current;
    if (image?.complete && image.naturalWidth > 0) void prepareFrame(image);
  }, [prepareFrame]);

  return <img ref={imageRef} className="media-image-stage-original" src={media.original_url}
    alt={media.original_filename} decoding="async" data-loaded={displayed}
    aria-hidden={hiddenFromAccessibility || undefined}
    onLoad={(event) => void prepareFrame(event.currentTarget)} onError={onError} />;
}
