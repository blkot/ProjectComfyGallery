export function hasShortcutModifier(event: KeyboardEvent): boolean {
  return event.altKey || event.ctrlKey || event.metaKey || event.shiftKey;
}

export function isShortcutBlockedTarget(
  target: EventTarget | null,
  options: { allowVideo?: boolean } = {},
): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  if (options.allowVideo && target.tagName === "VIDEO") return false;
  return [
    "A",
    "BUTTON",
    "INPUT",
    "SELECT",
    "SUMMARY",
    "TEXTAREA",
  ].includes(target.tagName);
}
