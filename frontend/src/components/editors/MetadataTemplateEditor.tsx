"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";

interface MetadataTemplateEditorProps {
  tabId: string;
}

interface Templates {
  domains: string[];
  processes: string[];
  tag_presets: string[];
}

function TemplateSection({
  title,
  items,
  field,
  onAdd,
  onRemove,
}: {
  title: string;
  items: string[];
  field: string;
  onAdd: (field: string, value: string) => void;
  onRemove: (field: string, value: string) => void;
}) {
  const [input, setInput] = useState("");

  const handleAdd = () => {
    const v = input.trim();
    if (!v) return;
    onAdd(field, v);
    setInput("");
  };

  return (
    <div>
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {items.map((item) => (
          <span
            key={item}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded-md bg-muted border"
          >
            {item}
            <button
              onClick={() => onRemove(field, item)}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
        {items.length === 0 && (
          <span className="text-xs text-muted-foreground">항목 없음</span>
        )}
      </div>
      <div className="flex gap-1.5">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.nativeEvent.isComposing && handleAdd()}
          placeholder="새 항목 입력..."
          className="flex-1 text-xs border rounded px-2 py-1 bg-background"
        />
        <button
          onClick={handleAdd}
          disabled={!input.trim()}
          className="px-2 py-1 text-xs rounded bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

export function MetadataTemplateEditor({ tabId: _tabId }: MetadataTemplateEditorProps) {
  const [templates, setTemplates] = useState<Templates | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/metadata/templates")
      .then((r) => r.json())
      .then((d) => { setTemplates(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const handleAdd = useCallback(async (field: string, value: string) => {
    try {
      const res = await fetch("/api/metadata/templates/add", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value }),
      });
      if (!res.ok) throw new Error("Failed");
      const updated = await res.json();
      setTemplates(updated);
      toast.success(`"${value}" 추가됨`);
    } catch {
      toast.error("추가 실패");
    }
  }, []);

  const handleRemove = useCallback(async (field: string, value: string) => {
    try {
      const res = await fetch("/api/metadata/templates/remove", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ field, value }),
      });
      if (!res.ok) throw new Error("Failed");
      const updated = await res.json();
      setTemplates(updated);
      toast.success(`"${value}" 삭제됨`);
    } catch {
      toast.error("삭제 실패");
    }
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">로딩 중...</p>
      </div>
    );
  }

  if (!templates) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <p className="text-sm">템플릿 로드 실패</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h2 className="text-lg font-bold">메타데이터 템플릿 관리</h2>
        <p className="text-sm text-muted-foreground mt-1">
          문서 메타데이터의 기본 선택지를 관리합니다. 여기서 추가/삭제한 항목이 에디터의 Domain, Process 드롭다운에 반영됩니다.
        </p>
      </div>

      <div className="border rounded-lg p-4 space-y-5">
        <TemplateSection
          title="Domain (업무 도메인)"
          items={templates.domains}
          field="domains"
          onAdd={handleAdd}
          onRemove={handleRemove}
        />

        <div className="border-t" />

        <TemplateSection
          title="Process (업무 프로세스)"
          items={templates.processes}
          field="processes"
          onAdd={handleAdd}
          onRemove={handleRemove}
        />

        <div className="border-t" />

        <TemplateSection
          title="Tag Presets (자주 사용하는 태그)"
          items={templates.tag_presets}
          field="tag_presets"
          onAdd={handleAdd}
          onRemove={handleRemove}
        />
      </div>
    </div>
  );
}
