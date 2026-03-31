"use client";

import { FileText, Hash } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface SearchResultItemProps {
  title: string;
  path: string;
  snippet: string;
  tags: string[];
  query: string;
  score?: number;
  status?: string;
  onClick: () => void;
}

function highlightMatches(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const terms = query
    .toLowerCase()
    .match(/[가-힣a-z0-9]+/g)
    ?.filter((t) => t.length >= 1);
  if (!terms || terms.length === 0) return text;

  const pattern = new RegExp(`(${terms.map(escapeRegex).join("|")})`, "gi");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    pattern.test(part) ? (
      <mark key={i} className="bg-yellow-200/60 dark:bg-yellow-500/30 rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function pathBreadcrumb(path: string): string {
  const parts = path.split("/");
  if (parts.length <= 1) return "";
  return parts.slice(0, -1).join(" / ");
}

export function SearchResultItem({
  title,
  path,
  snippet,
  tags,
  query,
  status,
  onClick,
}: SearchResultItemProps) {
  const breadcrumb = pathBreadcrumb(path);

  return (
    <button
      className="w-full flex items-start gap-3 px-3 py-2 text-left rounded-lg hover:bg-muted/60 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <FileText className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {highlightMatches(title, query)}
          </span>
          {status && status !== "" && (
            <Badge
              variant="outline"
              className={`text-[10px] px-1 py-0 ${
                status === "approved"
                  ? "border-green-500 text-green-600"
                  : status === "deprecated"
                  ? "border-red-400 text-red-500"
                  : status === "review"
                  ? "border-blue-400 text-blue-500"
                  : "border-gray-400 text-gray-500"
              }`}
            >
              {status}
            </Badge>
          )}
        </div>
        {breadcrumb && (
          <div className="text-[11px] text-muted-foreground truncate">
            {breadcrumb}
          </div>
        )}
        {snippet && (
          <div className="text-xs text-muted-foreground/80 mt-0.5 line-clamp-2">
            {highlightMatches(snippet, query)}
          </div>
        )}
        {tags.length > 0 && (
          <div className="flex items-center gap-1 mt-1 flex-wrap">
            <Hash className="h-3 w-3 text-muted-foreground/60" />
            {tags.slice(0, 4).map((tag) => (
              <span
                key={tag}
                className="text-[10px] px-1.5 py-0 rounded-full bg-muted text-muted-foreground"
              >
                {tag}
              </span>
            ))}
            {tags.length > 4 && (
              <span className="text-[10px] text-muted-foreground">
                +{tags.length - 4}
              </span>
            )}
          </div>
        )}
      </div>
    </button>
  );
}
