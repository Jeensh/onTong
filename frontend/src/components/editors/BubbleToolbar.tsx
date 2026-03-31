"use client";

import type { Editor } from "@tiptap/react";
import { BubbleMenu } from "@tiptap/react/menus";
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
  Quote,
} from "lucide-react";

interface BubbleToolbarProps {
  editor: Editor;
}

interface BtnProps {
  onClick: () => void;
  active?: boolean;
  children: React.ReactNode;
  title: string;
}

function Btn({ onClick, active, children, title }: BtnProps) {
  return (
    <button
      onClick={onClick}
      className={`p-1.5 rounded hover:bg-white/20 transition-colors ${
        active ? "bg-white/25 text-white" : "text-white/80"
      }`}
      title={title}
    >
      {children}
    </button>
  );
}

function Sep() {
  return <div className="w-px h-4 bg-white/20 mx-0.5" />;
}

export function BubbleToolbar({ editor }: BubbleToolbarProps) {
  return (
    <BubbleMenu
      editor={editor}
      className="flex items-center gap-0.5 px-1.5 py-1 rounded-lg bg-zinc-800 shadow-xl border border-zinc-700"
    >
      <Btn
        onClick={() => editor.chain().focus().toggleBold().run()}
        active={editor.isActive("bold")}
        title="굵게"
      >
        <Bold className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleItalic().run()}
        active={editor.isActive("italic")}
        title="기울임"
      >
        <Italic className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleStrike().run()}
        active={editor.isActive("strike")}
        title="취소선"
      >
        <Strikethrough className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleCode().run()}
        active={editor.isActive("code")}
        title="인라인 코드"
      >
        <Code className="h-3.5 w-3.5" />
      </Btn>

      <Sep />

      <Btn
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
        active={editor.isActive("heading", { level: 1 })}
        title="제목 1"
      >
        <Heading1 className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        active={editor.isActive("heading", { level: 2 })}
        title="제목 2"
      >
        <Heading2 className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
        active={editor.isActive("heading", { level: 3 })}
        title="제목 3"
      >
        <Heading3 className="h-3.5 w-3.5" />
      </Btn>

      <Sep />

      <Btn
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        active={editor.isActive("bulletList")}
        title="글머리 기호"
      >
        <List className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        active={editor.isActive("orderedList")}
        title="번호 매기기"
      >
        <ListOrdered className="h-3.5 w-3.5" />
      </Btn>
      <Btn
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        active={editor.isActive("blockquote")}
        title="인용"
      >
        <Quote className="h-3.5 w-3.5" />
      </Btn>
    </BubbleMenu>
  );
}
