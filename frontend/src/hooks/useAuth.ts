"use client";

import { useEffect, useState } from "react";
import type { User, AccessInfo } from "@/types/auth";
import { fetchCurrentUser } from "@/lib/api/auth";

let cachedUser: User | null = null;

export function useAuth() {
  const [user, setUser] = useState<User | null>(cachedUser);
  const [loading, setLoading] = useState(!cachedUser);

  useEffect(() => {
    if (cachedUser) return;
    fetchCurrentUser()
      .then((u) => {
        cachedUser = u;
        setUser(u);
      })
      .finally(() => setLoading(false));
  }, []);

  function checkAccess(
    acl: {
      owner?: string;
      read?: string[];
      write?: string[];
      manage?: string[];
    } | null,
  ): AccessInfo {
    if (!user)
      return { canRead: false, canWrite: false, canManage: false, isOwner: false };
    if (user.roles.includes("admin")) {
      return { canRead: true, canWrite: true, canManage: true, isOwner: false };
    }
    const isOwner = acl?.owner === user.id;
    const userPrincipals = [
      `@${user.id}`,
      ...user.groups,
      ...user.roles,
      "all",
    ];

    const matches = (allowed: string[]) =>
      allowed.some((p) => userPrincipals.includes(p));

    return {
      canRead: isOwner || matches(acl?.read ?? []),
      canWrite: isOwner || matches(acl?.write ?? []),
      canManage: isOwner || matches(acl?.manage ?? []),
      isOwner,
    };
  }

  return { user, loading, checkAccess };
}
