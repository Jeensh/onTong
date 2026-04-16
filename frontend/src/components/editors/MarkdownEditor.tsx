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
import { DocumentInfoBar } from "./DocumentInfoBar";
import { DocumentInfoDrawer } from "./DocumentInfoDrawer";
import { LineageWidget } from "./LineageWidget";
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

import { getCurrentUserName } from "@/lib/auth/currentUser";
import { fetchACL } from "@/lib/api/acl";
import { useAuth } from "@/hooks/useAuth";

export function MarkdownEditor({ filePath, tabId }: MarkdownEditorProps) {
  const { checkAccess } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noWriteAccess, setNoWriteAccess] = useState(false);
  const [sourceMode, setSourceMode] = useState(false);
  const [sourceText, setSourceText] = useState("");
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [metadata, setMetadata] = useState<DocumentMetadata>(emptyMetadata());
  const setDirty = useWorkspaceStore((s) => s.setDirty);
  const isDirty = useWorkspaceStore((s) => s.tabs.find((t) => t.id === tabId)?.isDirty ?? false);
  const openTab = useWorkspaceStore((s) => s.openTab);
  const agentDiff = useWorkspaceStore((s) => s.agentDiff);
  const clearAgentDiff = useWorkspaceStore((s) => s.clearAgentDiff);
  const agentWrite = useWorkspaceStore((s) => s.agentWrite);
  const clearAgentWrite = useWorkspaceStore((s) => s.clearAgentWrite);
  const refreshTree = useWorkspaceStore((s) => s.refreshTree);
  const [diffNewContent, setDiffNewContent] = useState<string | null>(null);
  const [lockedBy, setLockedBy] = useState<string | null>(null);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [indexPending, setIndexPending] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTab, setDrawerTab] = useState("metadata");
  const [confidenceData, setConfidenceData] = useState<{
    score: number; tier: string; stale: boolean; stale_months: number;
    signals: Record<string, number>; citation_count: number;
    newer_alternatives: Array<{ path: string; title: string; confidence_score: number; confidence_tier: string }>;
  } | null>(null);
  const [feedbackData, setFeedbackData] = useState<{
    verified_count: number; needs_update_count: number;
    last_verified_at: number; last_verified_by: string;
  } | null>(null);
  const [linkedDocsCount, setLinkedDocsCount] = useState(0);
  const originalContentRef = useRef("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadedRef = useRef(false);
  const prevFilePathRef = useRef(filePath);
  const openTabRef = useRef(openTab);
  openTabRef.current = openTab;
  // Ref to always call the latest handleSave
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
          "prose max-w-none focus:outline-none min-h-[300px] px-6 py-4",
      },
    },
    onUpdate: () => {
      // Skip the update triggered by initial content load
      if (!loadedRef.current) return;
      setDirty(tabId, true);
    },
  });

  // Load file content
  useEffect(() => {
    let cancelled = false;

    async function load() {
      // Auto-save previous file if dirty before loading new one
      if (prevFilePathRef.current !== filePath && handleSaveRef.current) {
        try {
          await handleSaveRef.current(undefined, true);
        } catch {}
      }
      prevFilePathRef.current = filePath;

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
      const rawContent = html ?? editor.getHTML();
      if (!rawContent || typeof rawContent !== "string") return;
      const md = htmlToMarkdown(rawContent);
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
        if (!silent) {
          const msg = e instanceof Error ? e.message : String(e);
          toast.error("저장 실패", { description: msg, duration: 5000 });
        }
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

  // Set new content for diff view when agentDiff targets this file
  useEffect(() => {
    if (!agentDiff || agentDiff.filePath !== filePath) {
      setDiffNewContent(null);
      return;
    }
    // Pre-approval mode: newContent provided directly from SSE
    if (agentDiff.newContent) {
      setDiffNewContent(agentDiff.newContent);
      return;
    }
    // Post-approval mode (legacy): fetch from server
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

  const resolveApproval = useCallback(async (approved: boolean) => {
    if (!agentDiff?.actionId || !agentDiff?.sessionId) return;
    try {
      await fetch("/api/approval/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: agentDiff.sessionId,
          action_id: agentDiff.actionId,
          approved,
        }),
      });
      if (approved) {
        refreshTree();
        toast.success("문서가 수정되었습니다");
      } else {
        toast.info("수정이 취소되었습니다");
      }
    } catch {
      toast.error("승인 처리 실패");
    }
  }, [agentDiff, refreshTree]);

  const handleDiffAction = useCallback(
    async (action: DiffAction, partialContent?: string) => {
      const isPreApproval = !!agentDiff?.actionId;

      if (action === "revert") {
        if (isPreApproval) {
          // Pre-approval: reject — don't save anything
          await resolveApproval(false);
        } else {
          // Post-approval: restore old content
          const oldContent = agentDiff?.oldContent;
          if (oldContent !== undefined) {
            const { parseFrontmatter: pf, mergeFrontmatterAndBody: mf } = await import(
              "@/lib/markdown/frontmatterSync"
            );
            const currentRaw = await fetchFile(filePath).then((w) => w.raw_content ?? "");
            const meta = pf(currentRaw);
            const full = mf(meta, oldContent);
            await saveFile(filePath, full);
            reloadEditor(oldContent);
          }
        }
      } else if (action === "accept") {
        if (isPreApproval) {
          // Pre-approval: approve via API (backend saves the file)
          await resolveApproval(true);
          // Reload with new content from server
          reloadEditor();
        } else if (partialContent) {
          // Post-approval partial apply
          const { parseFrontmatter: pf, mergeFrontmatterAndBody: mf } = await import(
            "@/lib/markdown/frontmatterSync"
          );
          const currentRaw = await fetchFile(filePath).then((w) => w.raw_content ?? "");
          const meta = pf(currentRaw);
          const full = mf(meta, partialContent);
          await saveFile(filePath, full);
          reloadEditor(partialContent);
        } else {
          // Post-approval accept all
          reloadEditor();
        }
      } else if (action === "edit") {
        if (isPreApproval) {
          // Approve first (save the AI content), then let user edit
          await resolveApproval(true);
        }
        reloadEditor();
      }
      clearAgentDiff();
      setDiffNewContent(null);
    },
    [agentDiff, clearAgentDiff, filePath, reloadEditor, resolveApproval]
  );

  // Lock acquisition + auto-refresh (via central lockManager) + cleanup
  useEffect(() => {
    if (!filePath.endsWith(".md")) return;

    acquireLock(filePath, getCurrentUserName()).then((res) => {
      if (res.locked && res.user === getCurrentUserName()) {
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
      releaseLock(filePath, getCurrentUserName()).catch(() => {});
    };
  }, [filePath, editor]);

  // ACL permission check — set read-only if no write access
  useEffect(() => {
    fetchACL(filePath).then((acl) => {
      const access = checkAccess(acl);
      if (!access.canWrite) {
        setNoWriteAccess(true);
        setIsReadOnly(true);
        editor?.setEditable(false);
      } else {
        setNoWriteAccess(false);
      }
    }).catch(() => {});
  }, [filePath, editor, checkAccess]);

  // Cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Fetch confidence + feedback data (lifted from TrustBanner)
  useEffect(() => {
    if (!filePath) return;
    let cancelled = false;
    const base = typeof window !== "undefined" && window.location.hostname === "localhost"
      ? "http://localhost:8001" : "";
    Promise.all([
      fetch(`${base}/api/wiki/confidence/${encodeURIComponent(filePath)}`).then((r) => r.ok ? r.json() : null),
      fetch(`${base}/api/wiki/feedback/${encodeURIComponent(filePath)}`).then((r) => r.ok ? r.json() : null),
    ]).then(([conf, fb]) => {
      if (cancelled) return;
      if (conf && typeof conf.score === "number") setConfidenceData(conf);
      if (fb) setFeedbackData(fb);
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [filePath]);

  // Keyboard shortcut: Cmd+I to toggle drawer
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "i") {
        e.preventDefault();
        setDrawerOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const handleToggleDrawer = useCallback(() => setDrawerOpen((v) => !v), []);
  const handleOpenDrawerTab = useCallback((tab: string) => {
    setDrawerTab(tab);
    setDrawerOpen(true);
  }, []);
  const handleCloseDrawer = useCallback(() => setDrawerOpen(false), []);
  const handleLinkedDocsCountChange = useCallback((total: number) => setLinkedDocsCount(total), []);

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

  // Show write preview if agent write is active for this file
  if (agentWrite && agentWrite.filePath === filePath) {
    const handleWriteApprove = async () => {
      try {
        await fetch("/api/approval/resolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: agentWrite.sessionId,
            action_id: agentWrite.actionId,
            approved: true,
          }),
        });
        clearAgentWrite();
        refreshTree();
        toast.success("문서가 생성되었습니다");
        // Reload editor with saved content
        reloadEditor();
      } catch {
        toast.error("문서 생성 실패");
      }
    };
    const handleWriteCancel = async () => {
      try {
        await fetch("/api/approval/resolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: agentWrite.sessionId,
            action_id: agentWrite.actionId,
            approved: false,
          }),
        });
        clearAgentWrite();
        toast.info("문서 생성이 취소되었습니다");
      } catch {
        toast.error("취소 처리 실패");
      }
    };
    const handleWriteEdit = async () => {
      // Approve (save file) then let user edit
      try {
        await fetch("/api/approval/resolve", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: agentWrite.sessionId,
            action_id: agentWrite.actionId,
            approved: true,
          }),
        });
        clearAgentWrite();
        refreshTree();
        reloadEditor();
      } catch {
        toast.error("처리 실패");
      }
    };

    return (
      <div className="flex flex-col h-full">
        <div className="flex items-center gap-3 px-4 py-2.5 border-b bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800">
          <span className="text-sm font-medium text-blue-800 dark:text-blue-200">
            AI가 생성한 문서 미리보기
          </span>
          <code className="text-xs bg-blue-100 dark:bg-blue-900/50 px-1.5 py-0.5 rounded text-blue-700 dark:text-blue-300">
            {agentWrite.filePath}
          </code>
          <div className="flex-1" />
          <button
            onClick={handleWriteApprove}
            className="inline-flex items-center gap-1 rounded-md bg-green-600 px-3 py-1 text-xs text-white hover:bg-green-700"
          >
            저장
          </button>
          <button
            onClick={handleWriteEdit}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1 text-xs text-primary-foreground hover:bg-primary/90"
          >
            직접 편집
          </button>
          <button
            onClick={handleWriteCancel}
            className="inline-flex items-center gap-1 rounded-md bg-muted px-3 py-1 text-xs text-muted-foreground hover:bg-muted/80"
          >
            취소
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          <div className="prose dark:prose-invert max-w-none" dangerouslySetInnerHTML={{
            __html: markdownToHtml(agentWrite.content),
          }} />
        </div>
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
      {isReadOnly && noWriteAccess && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted text-muted-foreground text-sm border-b">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          <span>편집 권한이 없습니다 (읽기 전용)</span>
        </div>
      )}
      {isReadOnly && lockedBy && !noWriteAccess && (
        <div className="flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200 text-sm border-b border-amber-200 dark:border-amber-800">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
          <span>{lockedBy} 님이 편집 중입니다 (읽기 전용)</span>
        </div>
      )}
      <DocumentInfoBar
        filePath={filePath}
        metadata={metadata}
        drawerOpen={drawerOpen}
        onToggleDrawer={handleToggleDrawer}
        onOpenDrawerTab={handleOpenDrawerTab}
        confidenceData={confidenceData}
        feedbackData={feedbackData}
        onConfidenceUpdate={setConfidenceData}
        onFeedbackUpdate={setFeedbackData}
        linkedDocsCounts={{ total: linkedDocsCount }}
      />
      <LineageWidget filePath={filePath} />
      {/* Drawer sits between InfoBar and editor content — relative container for overlay */}
      <div className="relative flex-1 min-h-0 flex flex-col">
        <DocumentInfoDrawer
          open={drawerOpen}
          activeTab={drawerTab}
          onTabChange={setDrawerTab}
          onClose={handleCloseDrawer}
          filePath={filePath}
          metadata={metadata}
          content={currentBodyText}
          onMetadataChange={handleMetadataChange}
          confidenceData={confidenceData}
          feedbackData={feedbackData}
          onConfidenceUpdate={setConfidenceData}
          onFeedbackUpdate={setFeedbackData}
          onConnectionCountChange={handleLinkedDocsCountChange}
          isDirty={isDirty}
          onSave={handleSave}
        />
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
            <div className="pb-16">
              <EditorContent editor={editor} />
            </div>
            {editor && <BubbleToolbar editor={editor} />}
            {editor && <SlashMenu editor={editor} />}
            {editor && <TableContextMenu editor={editor} />}
          </div>
        )}
      </div>

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
