/**
 * Light frontend DSL parser — strips prefix tokens (folder:X, author:@Y, tag:Z, ...)
 * from a search input string and promotes them to a FilterSpec patch.
 *
 * Intentionally narrower than the backend Boolean DSL (filter_dsl.py):
 *   - No AND/OR/NOT operators
 *   - No parens
 *   - No quoted values (future polish)
 * Tokens are simple `key:value` pairs separated by whitespace. Unknown tokens
 * stay in the residual query. The backend's full DSL is still reachable via
 * the `filters.boolean` field from the FilterSheet.
 */

import type { FilterSpec, TagFilter } from "./useSearchStore";

const TOKEN_RE = /(\S+?):(\S+)/g;

interface ParsedLight {
  query: string;
  patch: Partial<FilterSpec>;
}

function pushArray<K extends keyof FilterSpec>(
  patch: Partial<FilterSpec>,
  key: K,
  value: string
) {
  const existing = (patch[key] ?? []) as string[];
  if (!existing.includes(value)) existing.push(value);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (patch as any)[key] = existing;
}

function pushTag(patch: Partial<FilterSpec>, value: string, exclude = false) {
  const current: TagFilter = patch.tags ?? {};
  const bucket = exclude ? "exclude" : "include";
  const arr = [...(current[bucket] ?? [])];
  if (!arr.includes(value)) arr.push(value);
  patch.tags = { ...current, [bucket]: arr };
}

export function parseLightDSL(input: string): ParsedLight {
  const patch: Partial<FilterSpec> = {};
  const matched: Array<{ start: number; end: number }> = [];

  for (const m of input.matchAll(TOKEN_RE)) {
    const [full, rawKey, rawValue] = m;
    const key = rawKey.toLowerCase();
    const value = rawValue.trim();
    if (!value) continue;

    let consumed = true;
    switch (key) {
      case "folder":
      case "folders":
        pushArray(patch, "folders", value);
        break;
      case "author":
      case "authors":
        pushArray(patch, "authors", value.startsWith("@") ? value : `@${value}`);
        break;
      case "tag":
      case "tags":
        pushTag(patch, value, false);
        break;
      case "-tag":
        pushTag(patch, value, true);
        break;
      case "type":
      case "types":
        pushArray(patch, "types", value);
        break;
      case "status":
      case "statuses":
        pushArray(patch, "statuses", value);
        break;
      case "acl":
        pushArray(patch, "acl", value);
        break;
      case "mtime_from":
      case "since":
        patch.mtime_from = value;
        break;
      case "mtime_to":
      case "until":
        patch.mtime_to = value;
        break;
      default:
        consumed = false;
    }

    if (consumed && m.index !== undefined) {
      matched.push({ start: m.index, end: m.index + full.length });
    }
  }

  // Strip matched ranges from input, collapse whitespace
  let query = input;
  if (matched.length) {
    matched.sort((a, b) => b.start - a.start);
    for (const { start, end } of matched) {
      query = query.slice(0, start) + query.slice(end);
    }
  }
  query = query.replace(/\s+/g, " ").trim();

  return { query, patch };
}
