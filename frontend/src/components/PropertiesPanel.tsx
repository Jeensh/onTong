"use client";

import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { fetchACL } from "@/lib/api/acl";
import { useAuth } from "@/hooks/useAuth";

interface PropertiesPanelProps {
  path: string;
  metadata?: {
    created_by?: string;
    updated_by?: string;
    created?: string;
    updated?: string;
    status?: string;
  };
  onClose: () => void;
  onOpenShare?: () => void;
}

export function PropertiesPanel({
  path, metadata, onClose, onOpenShare,
}: PropertiesPanelProps) {
  const { user, checkAccess } = useAuth();
  const [acl, setAcl] = useState<{
    owner?: string; read?: string[]; write?: string[]; manage?: string[];
    inherited?: boolean;
  } | null>(null);

  useEffect(() => {
    fetchACL(path).then(setAcl);
  }, [path]);

  const access = checkAccess(acl);

  // Determine permission source
  const permSource = acl?.inherited !== false
    ? `${path.split("/").slice(0, -1).join("/") || "루트"}/ 에서 상속`
    : "직접 설정됨";

  const myPerms: string[] = [];
  if (access.canRead) myPerms.push("읽기");
  if (access.canWrite) myPerms.push("쓰기");
  if (access.canManage) myPerms.push("관리");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="w-[360px] rounded-lg border bg-background p-4 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold">속성</h3>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-2 text-sm">
          <Row label="소유자" value={acl?.owner || "—"} />
          <Row label="생성일" value={metadata?.created || "—"} />
          <Row label="수정일" value={metadata?.updated || "—"} />
          <Row label="최종 수정자" value={metadata?.updated_by || "—"} />
          <Row label="상태" value={metadata?.status || "—"} />
          <div className="my-2 h-px bg-border" />
          <Row label="내 권한" value={myPerms.join(" · ") || "없음"} />
          <Row label="권한 출처" value={permSource} />
        </div>

        <div className="mt-4 flex justify-end gap-2">
          {access.canManage && onOpenShare && (
            <button
              onClick={() => { onClose(); onOpenShare(); }}
              className="rounded bg-primary px-3 py-1 text-sm text-primary-foreground hover:bg-primary/90"
            >
              공유 설정
            </button>
          )}
          <button onClick={onClose} className="rounded border px-3 py-1 text-sm hover:bg-muted">
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
