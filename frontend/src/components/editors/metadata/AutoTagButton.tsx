"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { suggestMetadata } from "@/lib/api/metadata";
import { toast } from "sonner";
import { Check, Loader2, Sparkles, X } from "lucide-react";
import type { MetadataSuggestion, DocumentMetadata } from "@/types";

interface AutoTagButtonProps {
  content: string;
  currentMetadata: DocumentMetadata;
  onAccept: (updates: Partial<DocumentMetadata>) => void;
}

export function AutoTagButton({
  content,
  currentMetadata,
  onAccept,
}: AutoTagButtonProps) {
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<MetadataSuggestion | null>(
    null
  );

  const handleSuggest = async () => {
    setLoading(true);
    setSuggestion(null);
    try {
      const result = await suggestMetadata(content, currentMetadata.tags);
      setSuggestion(result);
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

      {suggestion && suggestion.tags.length > 0 && (
        <>
          {suggestion.tags.map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className="gap-1 border-dashed pr-1"
            >
              {tag}
              <button
                type="button"
                onClick={() => acceptTag(tag)}
                className="ml-0.5 rounded-full hover:bg-green-500/20"
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
          ))}
          <Button
            variant="ghost"
            size="sm"
            className="h-6 text-xs"
            onClick={acceptAll}
          >
            모두 수락
          </Button>
        </>
      )}

      {suggestion && suggestion.reasoning && (
        <span className="text-xs text-muted-foreground ml-1">
          {suggestion.reasoning}
        </span>
      )}
    </div>
  );
}
