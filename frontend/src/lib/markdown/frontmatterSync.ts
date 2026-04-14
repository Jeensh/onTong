import type { DocumentMetadata } from "@/types";

const FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n?/;

/** Default empty metadata. */
export function emptyMetadata(): DocumentMetadata {
  return {
    domain: "",
    process: "",
    error_codes: [],
    tags: [],
    status: "draft",
    supersedes: "",
    superseded_by: "",
    related: [],
    created: "",
    updated: "",
    created_by: "",
    updated_by: "",
  };
}

/** Serialize metadata to YAML frontmatter string (including --- delimiters). */
export function serializeMetadataToFrontmatter(
  meta: DocumentMetadata
): string {
  const lines: string[] = [];

  if (meta.domain) lines.push(`domain: ${meta.domain}`);
  if (meta.process) lines.push(`process: ${meta.process}`);
  if (meta.status) lines.push(`status: ${meta.status}`);
  if (meta.supersedes) lines.push(`supersedes: ${meta.supersedes}`);
  if (meta.superseded_by) lines.push(`superseded_by: ${meta.superseded_by}`);
  if (meta.created_by) lines.push(`created_by: ${meta.created_by}`);
  if (meta.updated_by) lines.push(`updated_by: ${meta.updated_by}`);
  if (meta.created) lines.push(`created: '${meta.created}'`);
  if (meta.updated) lines.push(`updated: '${meta.updated}'`);

  if (meta.error_codes.length > 0) {
    lines.push("error_codes:");
    for (const ec of meta.error_codes) {
      lines.push(`  - ${ec}`);
    }
  }

  if (meta.tags.length > 0) {
    lines.push("tags:");
    for (const t of meta.tags) {
      lines.push(`  - ${t}`);
    }
  }

  if (meta.related.length > 0) {
    lines.push("related:");
    for (const r of meta.related) {
      lines.push(`  - ${r}`);
    }
  }

  if (lines.length === 0) return "";

  return `---\n${lines.join("\n")}\n---\n`;
}

/** Strip frontmatter block from raw content, returning just the body. */
export function stripFrontmatter(raw: string): string {
  const match = raw.match(FRONTMATTER_RE);
  if (!match) return raw;
  return raw.slice(match[0].length);
}

/** Parse frontmatter YAML into DocumentMetadata (simple parser, no yaml lib needed). */
export function parseFrontmatter(raw: string): DocumentMetadata {
  const match = raw.match(FRONTMATTER_RE);
  if (!match) return emptyMetadata();

  const yaml = match[1];
  const meta = emptyMetadata();

  // Simple line-by-line YAML parsing
  let currentKey = "";
  for (const line of yaml.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    // List item
    if (trimmed.startsWith("- ")) {
      const val = trimmed.slice(2).trim();
      if (currentKey === "tags") meta.tags.push(val);
      else if (currentKey === "error_codes") meta.error_codes.push(val);
      else if (currentKey === "related") meta.related.push(val);
      continue;
    }

    // Key: value
    const colonIdx = trimmed.indexOf(":");
    if (colonIdx === -1) continue;

    const key = trimmed.slice(0, colonIdx).trim();
    const value = trimmed.slice(colonIdx + 1).trim();
    currentKey = key;

    switch (key) {
      case "domain":
        meta.domain = value;
        break;
      case "process":
        meta.process = value;
        break;
      case "status":
        meta.status = value as DocumentMetadata["status"];
        break;
      case "supersedes":
        meta.supersedes = value;
        break;
      case "superseded_by":
        meta.superseded_by = value;
        break;
      case "author":
      case "created_by":
        meta.created_by = value;
        break;
      case "updated_by":
        meta.updated_by = value;
        break;
      case "created":
        meta.created = value.replace(/^'|'$/g, "");
        break;
      case "updated":
        meta.updated = value.replace(/^'|'$/g, "");
        break;
      case "tags":
      case "error_codes":
      case "related":
        // value might be inline like [a, b] or empty (list follows)
        if (value && value !== "[]") {
          const items = value
            .replace(/^\[/, "")
            .replace(/\]$/, "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          if (key === "tags") meta.tags = items;
          else if (key === "error_codes") meta.error_codes = items;
          else meta.related = items;
        }
        break;
    }
  }

  return meta;
}

/** Merge metadata and body into a single string with frontmatter. */
export function mergeFrontmatterAndBody(
  meta: DocumentMetadata,
  body: string
): string {
  const fm = serializeMetadataToFrontmatter(meta);
  if (!fm) return body;
  return fm + body;
}
