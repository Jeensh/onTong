"use client";

import type { Editor } from "@tiptap/react";
import {
  Bold,
  Italic,
  Strikethrough,
  Code,
  Heading1,
  Heading2,
  Heading3,
  List,
  ListOrdered,
  ListChecks,
  Quote,
  Minus,
  Table,
  Undo,
  Redo,
  Save,
  FileCode,
  Eye,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface EditorToolbarProps {
  editor: Editor | null;
  sourceMode: boolean;
  onToggleSource: () => void;
  onSave: () => void;
  saving: boolean;
}

interface ToolbarButtonProps {
  onClick: () => void;
  active?: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  title: string;
}

function ToolbarButton({
  onClick,
  active,
  disabled,
  children,
  title,
}: ToolbarButtonProps) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className={`h-7 w-7 p-0 ${active ? "bg-muted" : ""}`}
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </Button>
  );
}

export function EditorToolbar({
  editor,
  sourceMode,
  onToggleSource,
  onSave,
  saving,
}: EditorToolbarProps) {
  if (!editor) return null;

  return (
    <div className="flex items-center gap-0.5 px-2 py-1 border-b flex-wrap">
      {/* History */}
      <ToolbarButton
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        title="실행 취소"
      >
        <Undo className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        title="다시 실행"
      >
        <Redo className="h-3.5 w-3.5" />
      </ToolbarButton>

      <div className="w-px h-5 bg-border mx-1" />

      {/* Text formatting */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBold().run()}
        active={editor.isActive("bold")}
        title="굵게 (Ctrl+B)"
      >
        <Bold className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleItalic().run()}
        active={editor.isActive("italic")}
        title="기울임 (Ctrl+I)"
      >
        <Italic className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleStrike().run()}
        active={editor.isActive("strike")}
        title="취소선"
      >
        <Strikethrough className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleCode().run()}
        active={editor.isActive("code")}
        title="인라인 코드"
      >
        <Code className="h-3.5 w-3.5" />
      </ToolbarButton>

      <div className="w-px h-5 bg-border mx-1" />

      {/* Headings */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        active={editor.isActive("heading", { level: 1 })}
        title="제목 1"
      >
        <Heading1 className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        active={editor.isActive("heading", { level: 2 })}
        title="제목 2"
      >
        <Heading2 className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        active={editor.isActive("heading", { level: 3 })}
        title="제목 3"
      >
        <Heading3 className="h-3.5 w-3.5" />
      </ToolbarButton>

      <div className="w-px h-5 bg-border mx-1" />

      {/* Lists */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        active={editor.isActive("bulletList")}
        title="글머리 기호"
      >
        <List className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        active={editor.isActive("orderedList")}
        title="번호 매기기"
      >
        <ListOrdered className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleTaskList().run()}
        active={editor.isActive("taskList")}
        title="체크리스트"
      >
        <ListChecks className="h-3.5 w-3.5" />
      </ToolbarButton>

      <div className="w-px h-5 bg-border mx-1" />

      {/* Blocks */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        active={editor.isActive("blockquote")}
        title="인용"
      >
        <Quote className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
        title="구분선"
      >
        <Minus className="h-3.5 w-3.5" />
      </ToolbarButton>
      <ToolbarButton
        onClick={() =>
          editor
            .chain()
            .focus()
            .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
            .run()
        }
        title="테이블 삽입"
      >
        <Table className="h-3.5 w-3.5" />
      </ToolbarButton>

      <div className="flex-1" />

      {/* Mode toggle + Save */}
      <ToolbarButton
        onClick={onToggleSource}
        active={sourceMode}
        title={sourceMode ? "WYSIWYG 모드" : "소스 모드"}
      >
        {sourceMode ? (
          <Eye className="h-3.5 w-3.5" />
        ) : (
          <FileCode className="h-3.5 w-3.5" />
        )}
      </ToolbarButton>
      <ToolbarButton onClick={onSave} disabled={saving} title="저장 (Ctrl+S)">
        <Save className="h-3.5 w-3.5" />
      </ToolbarButton>
    </div>
  );
}
