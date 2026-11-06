/**
 * Vision Pro: Tabler Icons (MIT), Copyright (c) 2020-2026 Paweł Kuna.
 * https://github.com/tabler/tabler-icons/blob/main/icons/outline/device-vision-pro.svg
 * Civitai mark: Civitai's official Logo.tsx (Apache-2.0); gradients replaced
 * with flat fills for a compact, subdued toolbar. The mark identifies Civitai.
 * https://github.com/civitai/civitai/blob/main/src/components/Logo/Logo.tsx
 * License texts are distributed in /media-action-icons.LICENSE.txt.
 */
export type MediaActionIconName =
  | "favorite"
  | "vision-pro"
  | "download"
  | "slideshow"
  | "civitai"
  | "trash"
  | "restore";

export function MediaActionIcon({
  name,
  filled = false,
}: {
  name: MediaActionIconName;
  filled?: boolean;
}) {
  if (name === "civitai") {
    return (
      <svg className="media-action-icon" viewBox="0 0 20.4 23.2" aria-hidden="true" focusable="false">
        <path fill="#26364c" d="M1.5,6.6v10l8.7,5l8.7-5v-10l-8.7-5L1.5,6.6z" />
        <path fill="#7794b8" d="M10.2,4.7l5.9,3.4V15l-5.9,3.4L4.2,15V8.1L10.2,4.7 M10.2,1.6l-8.7,5v10l8.7,5l8.7-5v-10C18.8,6.6,10.2,1.6,10.2,1.6z" />
        <path fill="#dce3ec" d="M11.8,12.4l-1.7,1l-1.7-1v-1.9l1.7-1l1.7,1h2.1V9.3l-3.8-2.2L6.4,9.3v4.3l3.8,2.2l3.8-2.2v-1.2H11.8z" />
      </svg>
    );
  }

  return (
    <svg className="media-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {name === "favorite" ? (
        <path fill={filled ? "currentColor" : "none"} d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3-5.7-3-5.7 3 1.1-6.3-4.6-4.5 6.4-.9Z" />
      ) : null}
      {name === "vision-pro" ? (
        <path d="M12 7c1.143 0 2.235 .035 3.275 .104c1.017 .068 1.95 .207 2.798 .42c.813 .203 1.52 .505 2.119 .909a3.903 3.903 0 0 1 1.328 1.531c.326 .657 .48 1.48 .48 2.466c0 1.006 -.189 1.91 -.574 2.707c-.375 .779 -.886 1.396 -1.537 1.848a3.696 3.696 0 0 1 -2.16 .66c-.509 0 -.97 -.068 -1.382 -.21a5.84 5.84 0 0 1 -1.17 -.548a18.45 18.45 0 0 1 -1.045 -.695a9.104 9.104 0 0 0 -1.001 -.63a2.376 2.376 0 0 0 -1.13 -.301c-.373 0 -.75 .097 -1.132 .3c-.316 .17 -.65 .38 -1 .63c-.322 .23 -.67 .462 -1.047 .695a5.78 5.78 0 0 1 -1.168 .548c-.413 .142 -.872 .21 -1.378 .21a3.706 3.706 0 0 1 -2.165 -.659c-.651 -.452 -1.162 -1.07 -1.537 -1.848c-.385 -.798 -.574 -1.7 -.574 -2.709c-.004 -.98 .15 -1.802 .477 -2.46a3.897 3.897 0 0 1 1.33 -1.531c.6 -.403 1.307 -.704 2.12 -.907a16.088 16.088 0 0 1 2.8 -.423c1.04 -.071 2.13 -.107 3.273 -.107Z" />
      ) : null}
      {name === "download" ? <><path d="M12 3v12m-5-5 5 5 5-5" /><path d="M4 15v5h16v-5" /></> : null}
      {name === "slideshow" ? <><rect x="3" y="3" width="18" height="13" rx="2" /><path d="m10 7 5 3-5 3Z" fill="currentColor" stroke="none" /><path d="M12 16v5m-4 0 4-3 4 3" /></> : null}
      {name === "trash" ? <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7" /></> : null}
      {name === "restore" ? <><path d="M4 11a8 8 0 1 1 1.5 6M4 4v7h7" /><path d="M12 8v5l3 2" /></> : null}
    </svg>
  );
}
