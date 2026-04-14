import type { ACLEntry } from "@/types/auth";

export async function fetchACL(
  path: string,
): Promise<ACLEntry & { inherited: boolean }> {
  const res = await fetch(`/api/acl/${encodeURIComponent(path)}`);
  if (!res.ok) throw new Error("Failed to fetch ACL");
  return res.json();
}

export async function setACL(
  path: string,
  acl: {
    read: string[];
    write: string[];
    manage: string[];
    inherited: boolean;
  },
): Promise<ACLEntry> {
  const res = await fetch(`/api/acl/${encodeURIComponent(path)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, ...acl }),
  });
  if (!res.ok) throw new Error("Failed to set ACL");
  return res.json();
}
