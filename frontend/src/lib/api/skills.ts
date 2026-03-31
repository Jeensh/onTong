import type { SkillContext, SkillCreateRequest, SkillListResponse, SkillMeta } from "@/types";

export async function fetchSkills(): Promise<SkillListResponse> {
  const res = await fetch("/api/skills");
  if (!res.ok) throw new Error(`Failed to fetch skills: ${res.status}`);
  return res.json();
}

export async function createSkill(body: SkillCreateRequest): Promise<SkillMeta> {
  const res = await fetch("/api/skills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to create skill: ${res.status}`);
  }
  return res.json();
}

export async function deleteSkill(path: string): Promise<void> {
  const res = await fetch(`/api/skills/${encodeURIComponent(path)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Failed to delete skill: ${res.status}`);
}

export async function matchSkill(
  query: string
): Promise<{ match: { skill: SkillMeta; confidence: number } | null }> {
  const res = await fetch(`/api/skills/match?q=${encodeURIComponent(query)}`);
  if (!res.ok) return { match: null };
  return res.json();
}

export async function fetchSkillContext(path: string): Promise<SkillContext> {
  const res = await fetch(`/api/skills/${encodeURIComponent(path)}/context`);
  if (!res.ok) throw new Error(`Failed to fetch skill context: ${res.status}`);
  return res.json();
}

export async function moveSkill(path: string, newCategory: string): Promise<SkillMeta> {
  const res = await fetch(`/api/skills/${encodeURIComponent(path)}/move`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_category: newCategory }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to move skill: ${res.status}`);
  }
  return res.json();
}

export async function toggleSkill(
  path: string
): Promise<{ path: string; enabled: boolean }> {
  const res = await fetch(`/api/skills/${encodeURIComponent(path)}/toggle`, {
    method: "PATCH",
  });
  if (!res.ok) throw new Error(`Failed to toggle skill: ${res.status}`);
  return res.json();
}
