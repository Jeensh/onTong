import type { MetadataTagsResponse, MetadataSuggestion, MetadataTemplates } from "@/types";

export async function fetchAllTags(): Promise<MetadataTagsResponse> {
  const res = await fetch("/api/metadata/tags");
  if (!res.ok) throw new Error(`GET /api/metadata/tags failed: ${res.status}`);
  return res.json();
}

export async function fetchTemplates(): Promise<MetadataTemplates> {
  const res = await fetch("/api/metadata/templates");
  if (!res.ok) throw new Error(`GET /api/metadata/templates failed: ${res.status}`);
  return res.json();
}

export async function searchTags(query: string, limit = 15): Promise<string[]> {
  const res = await fetch(`/api/metadata/tags/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  const tags = data.tags || [];
  if (tags.length > 0 && typeof tags[0] === "object") {
    return tags.map((t: { name: string }) => t.name);
  }
  return tags;
}

export async function searchTagsWithCount(query: string, limit = 15): Promise<{ name: string; count: number }[]> {
  const res = await fetch(`/api/metadata/tags/search?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  const tags = data.tags || [];
  if (tags.length > 0 && typeof tags[0] === "object") {
    return tags;
  }
  return tags.map((t: string) => ({ name: t, count: 0 }));
}

export async function checkSimilarTags(tag: string): Promise<{ tag: string; count: number }[]> {
  const res = await fetch(`/api/metadata/tags/similar?tag=${encodeURIComponent(tag)}&top_k=5`);
  if (!res.ok) return [];
  const data = await res.json();
  return (data.similar || []).map((s: { tag: string; count: number }) => ({
    tag: s.tag,
    count: s.count,
  }));
}

export async function searchPaths(query: string, limit = 20): Promise<string[]> {
  const res = await fetch(`/api/wiki/search-path?q=${encodeURIComponent(query)}&limit=${limit}`);
  if (!res.ok) return [];
  const data = await res.json();
  return data.paths || [];
}

export async function suggestMetadata(
  content: string,
  existingTags: string[],
  options: { path?: string; related?: string[] } = {}
): Promise<MetadataSuggestion> {
  const res = await fetch("/api/metadata/suggest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content,
      existing_tags: existingTags,
      path: options.path,
      related: options.related ?? [],
    }),
  });
  if (!res.ok)
    throw new Error(`POST /api/metadata/suggest failed: ${res.status}`);
  return res.json();
}
