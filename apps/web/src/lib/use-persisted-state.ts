import { useEffect, useState, type Dispatch, type SetStateAction } from "react";

export type PersistedStateValidator<T> = (value: unknown) => value is T;

/**
 * Read a JSON-encoded preference from localStorage.
 *
 * Storage failures, malformed JSON, and values that fail validation all fall
 * back to the caller's default so a corrupted preference never breaks a page.
 */
export function readPersistedState<T>(
  key: string,
  fallback: T,
  validate?: PersistedStateValidator<T>,
): T {
  try {
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    const parsed: unknown = JSON.parse(raw);
    if (validate && !validate(parsed)) return fallback;
    return parsed as T;
  } catch {
    return fallback;
  }
}

/**
 * `useState` backed by localStorage. The value is written whenever it changes
 * and restored on the next visit, so view preferences survive reloads without
 * leaking into shareable URLs.
 */
export function usePersistedState<T>(
  key: string,
  fallback: T,
  validate?: PersistedStateValidator<T>,
): [T, Dispatch<SetStateAction<T>>] {
  const [value, setValue] = useState<T>(() =>
    readPersistedState(key, fallback, validate),
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      // The control remains usable when storage is unavailable.
    }
  }, [key, value]);

  return [value, setValue];
}
