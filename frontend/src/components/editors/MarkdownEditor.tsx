"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { TableKit } from "@tiptap/extension-table";
import { Image } from "@tiptap/extension-image";
import { TaskList } from "@tiptap/extension-task-list";
import { TaskItem } from "@tiptap/extension-task-item";
import { Placeholder } from "@tiptap/extension-placeholder";
import { useWorkspaceStore } from "@/lib/workspace/useWorkspaceStore";
import { fetchFile, saveFile, acquireLock, releaseLock } from "@/lib/api/wiki";
import { lockManager } from "@/lib/lock/lockManager";
import { DiffView, type DiffAction } from "./DiffView";
import { htmlToMarkdown, markdownToHtml } from "@/lib/tiptap/markdown";
import { SlashCommandExtension } from "@/lib/tiptap/slashCommand";
import { PasteHandlerExtension } from "@/lib/tiptap/pasteHandler";
import { WikiLinkNode } from "@/lib/tiptap/wikiLink";
import { resolveWikiLink } from "@/lib/search/useSearchStore";
import { BubbleToolbar } from "./BubbleToolbar";
import { SlashMenu } from "./SlashMenu";
import { TableContextMenu } from "./TableContextMenu";
import { MetadataTagBar } from "./metadata/MetadataTagBar";
import { LinkedDocsPanel } from "./LinkedDocsPanel";
import {
  emptyMetadata,
  parseFrontmatter,
  mergeFrontmatterAndBody,
} from "@/lib/markdown/frontmatterSync";
import type { DocumentMetadata } from "@/types";
import { toast } from "sonner";

interface MarkdownEditorProps {
  filePath: string;
  tabId: string;
}

// Simple session user ID (will be replaced by auth system later)
const SESSION_USER = typeof window !== "undefined"
  ? (sessionStorage.getItem("ontong_user") || (() => {
      const id = `user-${Math.random().toString(36).slice(2, 8)}`;
      sessionStorage.setItem("ontong_user", id);
      return id;
    })())
  : "unknown";

export function MarkdownEditor({ filePath, tabId }: MarkdownEditorProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sourceMode, setSourceMode] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [metadata, setMetadata] = useState<DocumentMetadata>(emptyMetadata());
  const setDirty = useWorkspaceStore((s) => s.setDirty);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const agentDiff = useWorkspaceStore((s) => s.agentDiff);
  const clearAgentDiff = useWorkspaceStore((s) => s.clearAgentDiff);
  const [diffNewContent, setDiffNewContent] = useState<string | null>(null);
  const [lockedBy, setLockedBy] = useState<string | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [indexPending, setIndexPending] = useState(false);
  const originalContentRef = useRef("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedRef = useRef(false);
  const openTabRef = useRef(openTab);
  openTabRef.current = openTab;
  // Ref to always call the latest handleSave from onUpdate debounce
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleSaveRef = useRef<(html?: string, silent?: boolean) => Promise<void>>(null as any);

  const handleWikiLinkClick = useCallback(async (target: string) => {
    const path = await resolveWikiLink(target);
    if (path) {
      openTabRef.current(path);
    } else {
      toast.error(`문서를 찾을 수 없습니다: ${target}`);
    }
  }, []);

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        codeBlock: false,
      }),
      TableKit,
      Image,
      TaskList,
      TaskItem.configure({ nested: true }),
      Placeholder.configure({
        placeholder: "내용을 입력하세요... (/ 로 블록 삽입)",
      }),
      WikiLinkNode.configure({
        onClickLink: handleWikiLinkClick,
      }),
      SlashCommandExtension,
      PasteHandlerExtension,
    ],
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none focus:outline-none min-h-[300px] px-6 py-4",
      },
    },
    onUpdate: ({ editor: ed }) => {
      // Skip the update triggered by initial content load
      if (!loadedRef.current) return;
      setDirty(tabId, true);
      // Debounced auto-save — use ref to always call latest handleSave
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        handleSaveRef.current?.(ed.getHTML(), true);
      }, 3000);
    },
  });

  // Load file content
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const wiki = await fetchFile(filePath);
        if (cancelled) return;

        // Parse metadata from raw_content if available, else from response metadata
        if (wiki.raw_content) {
          const parsed = parseFrontmatter(wiki.raw_content);
          setMetadata(parsed);
        } else if (wiki.metadata) {
          setMetadata(wiki.metadata);
        }

        // content from API already has frontmatter stripped
        const html = markdownToHtml(wiki.content);
        originalContentRef.current = wiki.content;
        loadedRef.current = false;
        editor?.commands.setContent(html);
        // Mark as loaded after setContent so onUpdate skip works
        requestAnimationFrame(() => {
          loadedRef.current = true;
        });
        setDirty(tabId, false);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    if (editor) load();

    return () => {
      cancelled = true;
    };
  }, [filePath, editor, tabId, setDirty]);

  // Save handler
  const handleSave = useCallback(
    async (html?: string, silent = false) => {
      if (!editor || savingRef.current) return;
      const content = html ?? editor.getHTML();
      const md = htmlToMarkdown(content);
      // Merge frontmatter with body for saving
      const fullContent = mergeFrontmatterAndBody(metadata, md);
      savingRef.current = true;
      setSaving(true);
      try {
        const saved = await saveFile(filePath, fullContent);
        originalContentRef.current = md;
        setDirty(tabId, false);
        // Update metadata from server response (timestamps, author injected by backend)
        if (saved.raw_content) {
          setMetadata(parseFrontmatter(saved.raw_content));
        } else if (saved.metadata) {
          setMetadata(saved.metadata);
        }
        if (!silent) toast.success("저장 완료");
        // Track indexing status (non-blocking)
        setIndexPending(true);
        const pollIndex = setInterval(async () => {
          try {
            const r = await fetch("/api/wiki/index-status");
            if (r.ok) {
              const data = await r.json();
              const paths = (data.pending || []).map((p: { path: string }) => p.path);
              if (!paths.includes(filePath)) {
                setIndexPending(false);
                clearInterval(pollIndex);
              }
            }
          } catch { /* ignore */ }
        }, 3000);
        // Auto-clear after 30s to avoid infinite polling
        setTimeout(() => { clearInterval(pollIndex); setIndexPending(false); }, 30000);
      } catch (e) {
        if (!silent) toast.error("저장 실패: " + (e instanceof Error ? e.message : String(e)));
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    },
    [editor, filePath, tabId, setDirty, metadata]
  );
  handleSaveRef.current = handleSave;

  // Ctrl+S
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        if (debounceRef.current) clearTimeout(debounceRef.current);
        handleSave();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSave]);

  // Source mode toggle
  const toggleSourceMode = useCallback(() => {
    if (!editor) return;
    if (!sourceMode) {
      // WYSIWYG → Source
      setSourceText(htmlToMarkdown(editor.getHTML()));
    } else {
      // Source → WYSIWYG
      const html = markdownToHtml(sourceText);
      editor.commands.setContent(html);
    }
    setSourceMode(!sourceMode);
  }, [editor, sourceMode, sourceText]);

  // Fetch new content for diff view when agentDiff targets this file
  useEffect(() => {
    if (!agentDiff || agentDiff.filePath !== filePath) {
      setDiffNewContent(null);
      return;
    }
    let cancelled = false;
    fetchFile(filePath).then((wiki) => {
      if (!cancelled) setDiffNewContent(wiki.content);
    }).catch(() => {
      if (!cancelled) clearAgentDiff();
    });
    return () => { cancelled = true; };
  }, [agentDiff, filePath, clearAgentDiff]);

  const reloadEditor = useCallback((content?: string) => {
    if (!editor) return;
    const load = content
      ? Promise.resolve(content)
      : fetchFile(filePath).then((wiki) => wiki.content);
    load.then((md) => {
      const html = markdownToHtml(md);
      originalContentRef.current = md;
      loadedRef.current = false;
      editor.commands.setContent(html);
      requestAnimationFrame(() => { loadedRef.current = true; });
      setDirty(tabId, false);
    });
  }, [editor, filePath, tabId, setDirty]);

  const handleDiffAction = useCallback(
    async (action: DiffAction, partialContent?: string) => {
      if (action === "revert") {
        // Restore old content
        const oldContent = agentDiff?.oldContent;
        if (oldContent !== undefined) {
          const { parseFrontmatter, mergeFrontmatterAndBody } = await import(
            "@/lib/markdown/frontmatterSync"
          );
          // Preserve current frontmatter, replace body with old content
          const currentRaw = await fetchFile(filePath).then((w) => w.raw_content ?? "");
          const meta = parseFrontmatter(currentRaw);
          const full = mergeFrontmatterAndBody(meta, oldContent);
          await saveFile(filePath, full);
          reloadEditor(oldContent);
        }
      } else if (action === "accept" && partialContent) {
        // Partial apply: save the partially reconstructed content
        const { parseFrontmatter, mergeFrontmatterAndBody } = await import(
          "@/lib/markdown/frontmatterSync"
        );
        const currentRaw = await fetchFile(filePath).then((w) => w.raw_content ?? "");
        const meta = parseFrontmatter(currentRaw);
        const full = mergeFrontmatterAndBody(meta, partialContent);
        await saveFile(filePath, full);
        reloadEditor(partialContent);
      } else if (action === "edit") {
        // Close diff, open editor with current (new) content
        reloadEditor();
      } else {
        // accept all — just close diff and reload
        reloadEditor();
      }
      clearAgentDiff();
      setDiffNewContent(null);
    },
    [agentDiff, clearAgentDiff, filePath, reloadEditor]
  );

  // Lock acquisition + auto-refresh (via central lockManager) + cleanup
  useEffect(() => {
    if (!filePath.endsWith(".md")) return;

    acquireLock(filePath, SESSION_USER).then((res) => {
      if (res.locked && res.user === SESSION_USER) {
        setLockedBy(null);
        setIsReadOnly(false);
        // Register with central lock manager for batched refresh
        lockManager.register(filePath);
      } else if (res.locked) {
        setLockedBy(res.user);
        setIsReadOnly(true);
        editor?.setEditable(false);
      }
    }).catch(() => {});

    return () => {
      lockManager.unregister(filePath);
      releaseLock(filePath, SESSION_USER).catch(() => {});
    };
  }, [filePath, editor]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleMetadataChange = useCallback(
    (newMeta: DocumentMetadata) => {
      setMetadata(newMeta);
      setDirty(tabId, true);
    },
    [tabId, setDirty]
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="text-sm">불러오는 중...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <div className="text-sm">로드 실패: {error}</div>
      </div>
    );
  }

  // Show diff view if agent edit diff is active for this file
  if (agentDiff && agentDiff.filePath === filePath && diffNewContent !== null) {
    return (
      <DiffView
        oldContent={agentDiff.oldContent}
        newContent={diffNewContent}
        filePath={filePath}
        onAction={handleDiffAction}
      />
    );
  }

  // Get current body text for auto-tag
  const currentBodyText = editor
    ? htmlToMarkdown(editor.getHTML())
    : originalContentRef.current;

  return (
    <div className="flex flex-col h-full relative">
      {isReadOnly && lockedBy && (
        <div className="flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200 text-sm border-b border-amber-200 dark:border-amber-800">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <span>{lockedBy} 님이 편집 중입니다 (읽기 전용)</span>
        </div>
      )}
      <MetadataTagBar
        metadata={metadata}
        content={currentBodyText}
        onChange={handleMetadataChange}
      />
      <LinkedDocsPanel filePath={filePath} />
      {sourceMode ? (
        <textarea
          className="flex-1 w-full p-6 font-mono text-sm bg-muted/30 resize-none focus:outline-none"
          value={sourceText}
          onChange={(e) => {
            setSourceText(e.target.value);
            setDirty(tabId, true);
          }}
        />
      ) : (
        <div className="flex-1 overflow-auto relative">
          <EditorContent editor={editor} />
          {editor && <BubbleToolbar editor={editor} />}
          {editor && <SlashMenu editor={editor} />}
          {editor && <TableContextMenu editor={editor} />}
        </div>
      )}

      {/* Floating action buttons */}
      <div className="absolute bottom-4 right-4 flex items-center gap-1.5 z-10">
        <button
          onClick={toggleSourceMode}
          className="p-2 rounded-full bg-background border shadow-md hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
          title={sourceMode ? "WYSIWYG 모드" : "소스 모드"}
        >
          {sourceMode ? (
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/></svg>
          ) : (
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 12.5 8 15l-2-2.5"/><path d="m14 12.5 2 2.5 2-2.5"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/></svg>
          )}
        </button>
        <button
          onClick={() => handleSave()}
          disabled={saving}
          className="p-2 rounded-full bg-primary text-primary-foreground shadow-md hover:bg-primary/90 transition-colors disabled:opacity-50"
          title="저장 (Ctrl+S)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/></svg>
        </button>
      </div>
      {indexPending && (
        <div className="absolute bottom-16 right-4 bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 text-xs px-3 py-1 rounded-full shadow-sm">
          검색 반영 대기 중...
        </div>
      )}
    </div>
  );
}
