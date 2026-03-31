"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

interface ACLEntry {
  path: string;
  read: string[];
  write: string[];
}

export function PermissionEditor() {
  const [acl, setAcl] = useState<Record<string, { read: string[]; write: string[] }>>({});
  const [loading, setLoading] = useState(true);
  const [newPath, setNewPath] = useState("");
  const [newRead, setNewRead] = useState("all");
  const [newWrite, setNewWrite] = useState("admin");

  const fetchAcl = useCallback(async () => {
    try {
      const res = await fetch("/api/acl");
      if (res.ok) {
        setAcl(await res.json());
      }
    } catch {
      toast.error("ACL 로드 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAcl();
  }, [fetchAcl]);

  const handleAdd = async () => {
    if (!newPath.trim()) return;
    const entry: ACLEntry = {
      path: newPath.trim(),
      read: newRead.split(",").map((s) => s.trim()).filter(Boolean),
      write: newWrite.split(",").map((s) => s.trim()).filter(Boolean),
    };
    const res = await fetch("/api/acl", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
    if (res.ok) {
      toast.success("ACL 저장됨");
      setNewPath("");
      fetchAcl();
    } else {
      toast.error("ACL 저장 실패");
    }
  };

  const handleRemove = async (path: string) => {
    const res = await fetch(`/api/acl?path=${encodeURIComponent(path)}`, {
      method: "DELETE",
    });
    if (res.ok) {
      toast.success("ACL 삭제됨");
      fetchAcl();
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">ACL 로딩 중...</p>
      </div>
    );
  }

  const entries = Object.entries(acl);

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h2 className="text-lg font-semibold mb-4">접근 권한 관리 (ACL)</h2>

      {/* Existing entries */}
      <div className="border rounded-lg overflow-hidden mb-6">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left px-3 py-2 font-medium">경로</th>
              <th className="text-left px-3 py-2 font-medium">읽기</th>
              <th className="text-left px-3 py-2 font-medium">쓰기</th>
              <th className="px-3 py-2 w-16"></th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-4 text-center text-muted-foreground">
                  ACL 규칙이 없습니다 (모든 사용자 접근 가능)
                </td>
              </tr>
            )}
            {entries.map(([path, { read, write }]) => (
              <tr key={path} className="border-t">
                <td className="px-3 py-2 font-mono text-xs">{path}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {read.map((r) => (
                      <span key={r} className="px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200 rounded text-xs">
                        {r}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {write.map((w) => (
                      <span key={w} className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200 rounded text-xs">
                        {w}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => handleRemove(path)}
                    className="text-xs text-destructive hover:underline"
                  >
                    삭제
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add new entry */}
      <div className="border rounded-lg p-4 bg-muted/30">
        <h3 className="text-sm font-medium mb-3">새 규칙 추가</h3>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <div>
            <label className="text-xs text-muted-foreground block mb-1">경로</label>
            <input
              type="text"
              value={newPath}
              onChange={(e) => setNewPath(e.target.value)}
              placeholder="예: hr/ 또는 finance/report.md"
              className="w-full px-2 py-1.5 text-sm border rounded bg-background"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">읽기 역할 (쉼표 구분)</label>
            <input
              type="text"
              value={newRead}
              onChange={(e) => setNewRead(e.target.value)}
              placeholder="all, hr-team, admin"
              className="w-full px-2 py-1.5 text-sm border rounded bg-background"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground block mb-1">쓰기 역할 (쉼표 구분)</label>
            <input
              type="text"
              value={newWrite}
              onChange={(e) => setNewWrite(e.target.value)}
              placeholder="hr-team, admin"
              className="w-full px-2 py-1.5 text-sm border rounded bg-background"
            />
          </div>
        </div>
        <button
          onClick={handleAdd}
          className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90"
        >
          추가
        </button>
      </div>

      <p className="text-xs text-muted-foreground mt-4">
        &quot;all&quot; = 모든 사용자, &quot;admin&quot; 역할은 항상 모든 접근 허용.
        폴더 경로는 &quot;/&quot;로 끝내면 하위 문서에 자동 상속됩니다.
      </p>
    </div>
  );
}
