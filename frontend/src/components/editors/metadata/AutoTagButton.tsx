"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { suggestMetadata } from "@/lib/api/metadata";
import { toast } from "sonner";
import { ArrowRight, Check, Loader2, Sparkles, X } from "lucide-react";
import type { MetadataSuggestion, DocumentMetadata } from "@/types";

interface AutoTagButtonProps {
  content: string;
  currentMetadata: DocumentMetadata;
  onAccept: (updates: Partial<DocumentMetadata>) => void;
  filePath?: string;
}

export function AutoTagButton({
  content,
  currentMetadata,
  onAccept,
  filePath,
}: AutoTagButtonProps) {
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<MetadataSuggestion | null>(
    null
  );

  const handleSuggest = async () => {
    setLoading(true);
    setSuggestion(null);
    try {
      const result = await suggestMetadata(content, currentMetadata.tags, {
        path: filePath,
        related: currentMetadata.related,
      });
      setSuggestion(result);
      const replacedCount = Object.keys(result.tag_replaced || {}).length;
      if (replacedCount > 0) {
        toast.success(`${replacedCount}개 태그가 기존 태그로 정규화되었습니다`);
      }
    } catch {
      toast.error("추천 실패");
    } finally {
      setLoading(false);
    }
  };

  const acceptAll = () => {
    if (!suggestion) return;
    const newTags = [
      ...currentMetadata.tags,
      ...suggestion.tags.filter((t) => !currentMetadata.tags.includes(t)),
    ];
    onAccept({
      domain: suggestion.domain || currentMetadata.domain,
      process: suggestion.process || currentMetadata.process,
      error_codes: [
        ...new Set([
          ...currentMetadata.error_codes,
          ...suggestion.error_codes,
        ]),
      ],
      tags: newTags,
    });
    setSuggestion(null);
  };

  const acceptTag = (tag: string) => {
    if (!suggestion) return;
    onAccept({
      tags: [...currentMetadata.tags, tag],
    });
    setSuggestion({
      ...suggestion,
      tags: suggestion.tags.filter((t) => t !== tag),
    });
  };

  /** Replace a new suggested tag with one of its existing alternatives. */
  const acceptAlternative = (originalTag: string, altTag: string) => {
    if (!suggestion) return;
    if (!currentMetadata.tags.includes(altTag)) {
      onAccept({ tags: [...currentMetadata.tags, altTag] });
    }
    setSuggestion({
      ...suggestion,
      tags: suggestion.tags.filter((t) => t !== originalTag),
    });
  };

  const rejectTag = (tag: string) => {
    if (!suggestion) return;
    setSuggestion({
      ...suggestion,
      tags: suggestion.tags.filter((t) => t !== tag),
    });
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Button
        variant="outline"
        size="sm"
        className="h-7 gap-1 text-xs"
        onClick={handleSuggest}
        disabled={loading || !content}
      >
        {loading ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <Sparkles className="h-3 w-3" />
        )}
        Auto-Tag
      </Button>

      {suggestion && (
        <>
          {suggestion.confidence > 0 && (
            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${
              suggestion.confidence >= 0.7
                ? "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400"
                : suggestion.confidence >= 0.5
                ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400"
                : "bg-red-100 text-red-600 dark:bg-red-900/40 dark:text-red-400"
            }`}>
              신뢰도 {Math.round(suggestion.confidence * 100)}%
            </span>
          )}

          {suggestion.domain && !currentMetadata.domain && (
            <Badge
              variant="outline"
              className="gap-1 border-dashed border-blue-300 pr-1"
            >
              <span className="text-[10px] text-muted-foreground">domain:</span>
              {suggestion.domain}
              <button
                type="button"
                onClick={() => { onAccept({ domain: suggestion.domain }); setSuggestion({ ...suggestion, domain: "" }); }}
                className="ml-0.5 rounded-full hover:bg-green-500/20"
              >
                <Check className="h-3 w-3 text-green-600" />
              </button>
            </Badge>
          )}

          {suggestion.process && !currentMetadata.process && (
            <Badge
              variant="outline"
              className="gap-1 border-dashed border-blue-300 pr-1"
            >
              <span className="text-[10px] text-muted-foreground">process:</span>
              {suggestion.process}
              <button
                type="button"
                onClick={() => { onAccept({ process: suggestion.process }); setSuggestion({ ...suggestion, process: "" }); }}
                className="ml-0.5 rounded-full hover:bg-green-500/20"
              >
                <Check className="h-3 w-3 text-green-600" />
              </button>
            </Badge>
          )}

          {suggestion.tags.length > 0 && suggestion.tags.map((tag) => {
            const alts = suggestion.tag_alternatives?.[tag] || [];
            return (
              <span key={tag} className="inline-flex items-center gap-1">
                <Badge
                  variant="outline"
                  className={`gap-1 border-dashed pr-1 ${
                    suggestion.confidence < 0.5 ? "opacity-50" : ""
                  }`}
                >
                  {tag}
                  <button
                    type="button"
                    onClick={() => acceptTag(tag)}
                    className="ml-0.5 rounded-full hover:bg-green-500/20"
                    title="이 태그를 그대로 추가"
                  >
                    <Check className="h-3 w-3 text-green-600" />
                  </button>
                  <button
                    type="button"
                    onClick={() => rejectTag(tag)}
                    className="rounded-full hover:bg-destructive/20"
                  >
                    <X className="h-3 w-3 text-destructive" />
                  </button>
                </Badge>
                {alts.length > 0 && (
                  <>
                    <ArrowRight className="h-3 w-3 text-muted-foreground" />
                    {alts.map((alt) => (
                      <button
                        key={alt.tag}
                        type="button"
                        onClick={() => acceptAlternative(tag, alt.tag)}
                        className="text-[10px] px-1.5 py-0.5 rounded border border-primary/30 bg-primary/10 hover:bg-primary/20"
                        title={`기존 태그 사용 (유사도 ${(1 - alt.distance).toFixed(2)})`}
                      >
                        {alt.tag}
                        <span className="ml-1 text-muted-foreground">({alt.count}건)</span>
                      </button>
                    ))}
                  </>
                )}
              </span>
            );
          })}

          {(suggestion.tags.length > 0 || suggestion.domain || suggestion.process) && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs"
              onClick={acceptAll}
            >
              모두 수락
            </Button>
          )}

          {suggestion.reasoning && (
            <span className="text-xs text-muted-foreground ml-1">
              {suggestion.reasoning}
            </span>
          )}
        </>
      )}
    </div>
  );
}
