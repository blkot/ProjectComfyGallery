export function resolveReviewPosition(
  rawPosition: string | null,
  currentCursor: number | undefined,
) {
  if (rawPosition !== null) {
    const requested = Number(rawPosition);
    if (Number.isInteger(requested) && requested >= 0) return requested;
  }
  return currentCursor ?? 0;
}
