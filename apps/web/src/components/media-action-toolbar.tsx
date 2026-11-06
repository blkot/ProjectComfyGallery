import type { RefObject } from "react";
import { Link } from "react-router";

import type { MediaDetail } from "../lib/api";
import { MediaActionIcon } from "./media-action-icon";
import { MediaContentRatingControl } from "./media-content-rating-control";
import { MediaFavoriteButton } from "./media-favorite-button";
import { MediaSpatialPreferenceButton } from "./media-spatial-preference-button";
import { MediaTrashButton } from "./media-trash-button";
import "./media-actions.css";

export function MediaActionToolbar({
  media,
  slideshowHref,
  civitaiHref,
  favoriteButtonRef,
  contentRatingShortcutRef,
}: {
  media: MediaDetail;
  slideshowHref: string;
  civitaiHref: string;
  favoriteButtonRef?: RefObject<HTMLButtonElement | null>;
  contentRatingShortcutRef?: RefObject<HTMLButtonElement | null>;
}) {
  return (
    <div className="media-action-toolbar" role="group" aria-label="Media actions">
      <MediaFavoriteButton mediaId={media.id} favorite={media.favorite} buttonRef={favoriteButtonRef} compact />
      <MediaContentRatingControl mediaId={media.id} rating={media.content_rating} shortcutButtonRef={contentRatingShortcutRef} compact />
      <MediaSpatialPreferenceButton mediaId={media.id} preferred={media.prefer_spatial_playback} compact />
      <a className="media-action-link" href={`${media.original_url}${media.original_url.includes("?") ? "&" : "?"}download=true`} aria-label="Download original" title="Download original">
        <MediaActionIcon name="download" />
      </a>
      <Link className="media-action-link" to={slideshowHref} aria-label="Start slideshow from here" title="Slideshow from here">
        <MediaActionIcon name="slideshow" />
      </Link>
      <Link className="media-action-link" to={civitaiHref} aria-label="Post to Civitai" title="Post to Civitai">
        <MediaActionIcon name="civitai" />
      </Link>
      <MediaTrashButton mediaId={media.id} isTrash={media.is_trash} compact />
    </div>
  );
}
