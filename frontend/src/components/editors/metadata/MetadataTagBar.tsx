"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { fetchAllTags } from "@/lib/api/metadata";
import type { DocumentMetadata, MetadataTagsResponse } from "@/types";
import { TagInput } from "./TagInput";
import { DomainSelect } from "./DomainSelect";
import { AutoTagButton } from "./AutoTagButton";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

interface MetadataTagBarProps {
  metadata: DocumentMetadata;
  content: string;
  onChange: (metadata: DocumentMetadata) => void;
}

export function MetadataTagBar({
  metadata,
  content,
  onChange,
}: MetadataTagBarProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [allTags, setAllTags] = useState<MetadataTagsResponse>({
    domains: [],
    processes: [],
    error_codes: [],
    tags: [],
  });
  const [templateDomains, setTemplateDomains] = useState<string[]>([]);
  const [templateProcesses, setTemplateProcesses] = useState<string[]>([]);

  useEffect(() => {
    fetchAllTags()
      .then(setAllTags)
      .catch(() => {});
    // Load templates for default options
    fetch("/api/metadata/templates")
      .then((r) => r.json())
      .then((t) => {
        setTemplateDomains(t.domains || []);
        setTemplateProcesses(t.processes || []);
      })
      .catch(() => {});
  }, []);

  const updateField = useCallback(
    <K extends keyof DocumentMetadata>(key: K, value: DocumentMetadata[K]) => {
      onChange({ ...metadata, [key]: value });
    },
    [metadata, onChange]
  );

  const handleAutoAccept = useCallback(
    (updates: Partial<DocumentMetadata>) => {
      onChange({ ...metadata, ...updates });
    },
    [metadata, onChange]
  );

  return (
    <div className="border-b bg-muted/20">
      <button
        type="button"
        className="flex items-center gap-1 px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground w-full"
        onClick={() => setCollapsed(!collapsed)}
      >
        {collapsed ? (
          <ChevronRight className="h-3 w-3 shrink-0" />
        ) : (
          <ChevronDown className="h-3 w-3 shrink-0" />
        )}
        <span className="shrink-0">Metadata</span>
        {collapsed && (metadata.domain || metadata.tags.length > 0 || metadata.status) && (
          <span className="ml-2 truncate text-muted-foreground/60">
            {metadata.status && (
              <span className={`inline-block rounded px-1 py-0 mr-1 text-[10px] font-medium ${
                metadata.status === "approved" ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400" :
                metadata.status === "deprecated" ? "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400" :
                metadata.status === "review" ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-400" :
                "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
              }`}>
                {metadata.status}
              </span>
            )}
            {[
              metadata.domain,
              metadata.process,
              ...metadata.tags.slice(0, 3),
            ]
              .filter(Boolean)
              .join(" · ")}
            {metadata.tags.length > 3 && ` +${metadata.tags.length - 3}`}
          </span>
        )}
      </button>

      {!collapsed && (
        <div className="px-4 pb-3 space-y-2">
          <div className="flex items-center gap-4 flex-wrap">
            <DomainSelect
              label="Domain"
              value={metadata.domain}
              options={[...new Set([...templateDomains, ...allTags.domains])]}
              onChange={(v) => updateField("domain", v)}
            />
            <DomainSelect
              label="Process"
              value={metadata.process}
              options={[...new Set([...templateProcesses, ...allTags.processes])]}
              onChange={(v) => updateField("process", v)}
            />
          </div>

          <div>
            <span className="text-xs text-muted-foreground mb-1 block">
              Tags
            </span>
            <TagInput
              tags={metadata.tags}
              suggestions={allTags.tags}
              onChange={(tags) => updateField("tags", tags)}
            />
          </div>

          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <span className="text-xs text-muted-foreground mb-1 block">
                Status
              </span>
              <select
                value={metadata.status || ""}
                onChange={(e) => updateField("status", e.target.value as DocumentMetadata["status"])}
                className="h-7 rounded-md border bg-background px-2 text-xs focus:outline-none focus:ring-1 focus:ring-ring"
              >
                <option value="">-- 미설정 --</option>
                <option value="draft">Draft</option>
                <option value="review">Review</option>
                <option value="approved">Approved</option>
                <option value="deprecated">Deprecated</option>
              </select>
            </div>
          </div>

          <AutoTagButton
            content={content}
            currentMetadata={metadata}
            onAccept={handleAutoAccept}
          />

          {/* Read-only audit info */}
          {(metadata.created || metadata.created_by || metadata.updated || metadata.updated_by) && (
            <div className="flex items-center gap-4 flex-wrap text-[11px] text-muted-foreground pt-1 border-t border-border/50">
              {metadata.created_by && (
                <span>작성자: <span className="text-foreground/70">{metadata.created_by}</span></span>
              )}
              {metadata.created && (
                <span>생성: <span className="text-foreground/70">{formatDate(metadata.created)}</span></span>
              )}
              {metadata.updated_by && (
                <span>최종 수정자: <span className="text-foreground/70">{metadata.updated_by}</span></span>
              )}
              {metadata.updated && (
                <span>최종 수정: <span className="text-foreground/70">{formatDate(metadata.updated)}</span></span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
