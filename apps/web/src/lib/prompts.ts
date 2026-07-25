type PromptLike = {
  role: string | null;
};

export function promptRoleRank(role: string | null): number {
  const normalized = (role ?? "")
    .trim()
    .toLocaleLowerCase()
    .replaceAll(/[\s-]+/g, "_");
  if (
    normalized === "positive" ||
    normalized === "main" ||
    normalized === "primary" ||
    normalized === "positive_prompt"
  ) {
    return 0;
  }
  if (normalized === "negative" || normalized === "negative_prompt") {
    return 2;
  }
  return 1;
}

export function orderPrompts<T extends PromptLike>(prompts: T[]): T[] {
  return [...prompts].sort(
    (left, right) => promptRoleRank(left.role) - promptRoleRank(right.role),
  );
}
