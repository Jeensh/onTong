"use client";

import { useEffect, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";

interface Position {
  x: number;
  y: number;
}

interface MenuItem {
  label: string;
  action: () => void;
  disabled?: boolean;
  separator?: boolean;
}

interface TableContextMenuProps {
  editor: Editor;
}

export function TableContextMenu({ editor }: TableContextMenuProps) {
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState<Position>({ x: 0, y: 0 });
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleContextMenu(e: MouseEvent) {
      const target = e.target as HTMLElement;
      const cell = target.closest("td, th");
      if (!cell) {
        setVisible(false);
        return;
      }

      // Check if inside the tiptap editor
      const editorEl = target.closest(".ProseMirror");
      if (!editorEl) return;

      e.preventDefault();
      setPosition({ x: e.clientX, y: e.clientY });
      setVisible(true);
    }

    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setVisible(false);
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setVisible(false);
    }

    document.addEventListener("contextmenu", handleContextMenu);
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("contextmenu", handleContextMenu);
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  if (!visible) return null;

  const items: MenuItem[] = [
    {
      label: "위에 행 추가",
      action: () => editor.chain().focus().addRowBefore().run(),
    },
    {
      label: "아래에 행 추가",
      action: () => editor.chain().focus().addRowAfter().run(),
    },
    {
      label: "행 삭제",
      action: () => editor.chain().focus().deleteRow().run(),
    },
    { label: "", action: () => {}, separator: true },
    {
      label: "왼쪽에 열 추가",
      action: () => editor.chain().focus().addColumnBefore().run(),
    },
    {
      label: "오른쪽에 열 추가",
      action: () => editor.chain().focus().addColumnAfter().run(),
    },
    {
      label: "열 삭제",
      action: () => editor.chain().focus().deleteColumn().run(),
    },
    { label: "", action: () => {}, separator: true },
    {
      label: "셀 병합",
      action: () => editor.chain().focus().mergeCells().run(),
    },
    {
      label: "셀 분할",
      action: () => editor.chain().focus().splitCell().run(),
    },
    { label: "", action: () => {}, separator: true },
    {
      label: "헤더 행 토글",
      action: () => editor.chain().focus().toggleHeaderRow().run(),
    },
    {
      label: "헤더 열 토글",
      action: () => editor.chain().focus().toggleHeaderColumn().run(),
    },
    { label: "", action: () => {}, separator: true },
    {
      label: "표 삭제",
      action: () => editor.chain().focus().deleteTable().run(),
    },
  ];

  return (
    <div
      ref={menuRef}
      className="fixed z-[9999] min-w-[160px] rounded-md border bg-popover py-1 shadow-lg"
      style={{ left: position.x, top: position.y }}
    >
      {items.map((item, i) =>
        item.separator ? (
          <div key={i} className="my-1 h-px bg-border" />
        ) : (
          <button
            key={i}
            type="button"
            className="w-full px-3 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
            disabled={item.disabled}
            onClick={() => {
              item.action();
              setVisible(false);
            }}
          >
            {item.label}
          </button>
        )
      )}
    </div>
  );
}
