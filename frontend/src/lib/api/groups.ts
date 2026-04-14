import type { Group } from "@/types/auth";

export async function fetchGroups(): Promise<Group[]> {
  const res = await fetch("/api/groups");
  if (!res.ok) throw new Error("Failed to fetch groups");
  return res.json();
}

export async function createGroup(body: {
  id: string;
  name: string;
  type: string;
  members: string[];
}): Promise<Group> {
  const res = await fetch("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to create group");
  return res.json();
}

export async function updateMembers(
  groupId: string,
  body: { add?: string[]; remove?: string[] },
): Promise<Group> {
  const res = await fetch(`/api/groups/${groupId}/members`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Failed to update members");
  return res.json();
}

export async function deleteGroup(groupId: string): Promise<void> {
  const res = await fetch(`/api/groups/${groupId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete group");
}
