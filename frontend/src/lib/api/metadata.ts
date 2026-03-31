import type { MetadataTagsResponse, MetadataSuggestion } from "@/types";

export async function fetchAllTags(): Promise<MetadataTagsResponse> {
  const res = await fetch("/api/metadata/tags");
  if (!res.ok) throw new Error(`GET /api/metadata/tags failed: ${res.status}`);
  return res.json();
}

export async function suggestMetadata(
  content: string,
  existingTags: string[]
): Promise<MetadataSuggestion> {
  const res = await fetch("/api/metadata/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, existing_tags: existingTags }),
  });
  if (!res.ok)
    throw new Error(`POST /api/metadata/suggest failed: ${res.status}`);
  return res.json();
}
