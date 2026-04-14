"use client";

import { useEffect, useState } from "react";
import { X, UserPlus, Trash2 } from "lucide-react";
import type { ACLEntry } from "@/types/auth";
import { fetchACL, setACL } from "@/lib/api/acl";
import { fetchGroups } from "@/lib/api/groups";

interface ShareDialogProps {
  path: string;
  onClose: () => void;
}

type PermLevel = "read" | "readwrite";

interface ShareEntry {
  principal: string;  // "@kim" or "인프라팀"
  level: PermLevel;
}

export function ShareDialog({ path, onClose }: ShareDialogProps) {
  const [entries, setEntries] = useState<ShareEntry[]>([]);
  const [inherited, setInherited] = useState(true);
  const [owner, setOwner] = useState("");
  const [search, setSearch] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchACL(path).then((acl) => {
      setOwner(acl.owner || "");
      setInherited(acl.inherited);
      // Build entries from read/write lists
      const map = new Map<string, PermLevel>();
      for (const p of acl.write || []) {
        if (p !== "all") map.set(p, "readwrite");
      }
      for (const p of acl.read || []) {
        if (p !== "all" && !map.has(p)) map.set(p, "read");
      }
      setEntries(Array.from(map, ([principal, level]) => ({ principal, level })));
    });
    fetchGroups().then((groups) => {
      setSuggestions(groups.map((g) => g.name));
    });
  }, [path]);

  async function handleSave() {
    setSaving(true);
    const read = entries.map((e) => e.principal);
    const write = entries.filter((e) => e.level === "readwrite").map((e) => e.principal);
    try {
      await setACL(path, { read, write, manage: [`@${owner}`], inherited });
    } finally {
      setSaving(false);
      onClose();
    }
  }

  function addPrincipal(name: string) {
    if (!name.trim()) return;
    const principal = name.startsWith("@") ? name : name;
    if (entries.some((e) => e.principal === principal)) return;
    setEntries([...entries, { principal, level: "read" }]);
    setSearch("");
  }

  function removePrincipal(principal: string) {
    setEntries(entries.filter((e) => e.principal !== principal));
  }

  function toggleLevel(principal: string) {
    setEntries(entries.map((e) =>
      e.principal === principal
        ? { ...e, level: e.level === "read" ? "readwrite" : "read" }
        : e
    ));
  }

  const filtered = suggestions.filter(
    (s) => s.includes(search) && !entries.some((e) => e.principal === s),
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[420px] rounded-lg border bg-background p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">공유 설정</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mb-3 text-xs text-muted-foreground">
          소유자: <span className="font-medium text-foreground">{owner || "—"}</span>
        </div>

        {/* Current permissions */}
        <div className="mb-3 max-h-[200px] space-y-1 overflow-y-auto">
          {entries.map((e) => (
            <div key={e.principal} className="flex items-center justify-between rounded px-2 py-1 hover:bg-muted">
              <span className="text-sm">{e.principal}</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => toggleLevel(e.principal)}
                  className="rounded px-2 py-0.5 text-xs border hover:bg-accent"
                >
                  {e.level === "readwrite" ? "읽기/쓰기" : "읽기"}
                </button>
                <button onClick={() => removePrincipal(e.principal)}
                        className="text-muted-foreground hover:text-destructive">
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Add principal */}
        <div className="relative mb-3">
          <div className="flex gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && search.trim()) {
                  addPrincipal(search.trim());
                }
              }}
              placeholder="사용자(@이름) 또는 그룹 추가"
              className="flex-1 rounded border px-2 py-1 text-sm"
            />
            <button
              onClick={() => addPrincipal(search.trim())}
              className="rounded border px-2 py-1 text-sm hover:bg-accent"
            >
              <UserPlus className="h-4 w-4" />
            </button>
          </div>
          {search && filtered.length > 0 && (
            <div className="absolute top-full z-10 mt-1 max-h-[120px] w-full overflow-y-auto rounded border bg-popover shadow-md">
              {filtered.slice(0, 8).map((s) => (
                <button
                  key={s}
                  onClick={() => addPrincipal(s)}
                  className="block w-full px-2 py-1 text-left text-sm hover:bg-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Inheritance toggle */}
        <label className="mb-4 flex items-center gap-2 text-xs">
          <input
            type="checkbox"
            checked={!inherited}
            onChange={(e) => setInherited(!e.target.checked)}
          />
          폴더 권한 상속 해제 (직접 관리)
        </label>

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1 text-sm hover:bg-muted">
            취소
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {saving ? "저장 중..." : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}
