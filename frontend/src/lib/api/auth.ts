import type { User } from "@/types/auth";

export async function fetchCurrentUser(): Promise<User> {
  const res = await fetch("/api/auth/me");
  if (!res.ok) throw new Error("Failed to fetch user");
  return res.json();
}
